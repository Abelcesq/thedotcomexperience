from datetime import datetime, timezone as dt_timezone

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.models import Profile
from . import stripe_utils
from .models import WebhookEvent


def join(request):
    """The /join/ page. Auth-first: logged-out visitors are sent to sign up, then back here."""
    if not request.user.is_authenticated:
        return redirect(f"{settings.LOGIN_URL}?next={reverse('join')}")
    profile = request.user.profile
    if profile.is_active_member:
        return redirect("profile")
    return render(request, "billing/join.html", {"profile": profile})


@login_required
@require_POST
def checkout(request):
    """Create a Checkout Session and redirect to hosted Stripe."""
    if not stripe_utils.configured():
        messages.error(request, "Payments aren't set up yet. Please check back soon.")
        return redirect("join")
    profile = request.user.profile
    success_url = f"{settings.SITE_URL}{reverse('profile')}?stripe=ok"
    cancel_url = f"{settings.SITE_URL}{reverse('join')}?stripe=cancel"
    try:
        session = stripe_utils.create_checkout_session(profile, success_url, cancel_url)
    except Exception as exc:  # noqa: BLE001 — surface a friendly message, log server-side
        import logging
        logging.getLogger("billing").exception("checkout session failed: %s", exc)
        messages.error(request, "We couldn't start checkout. Please try again.")
        return redirect("join")
    return redirect(session["url"], permanent=False)


@login_required
@require_POST
def customer_portal(request):
    """Redirect to the Stripe Customer Portal (manage card / invoices / cancel)."""
    if not stripe_utils.configured():
        messages.error(request, "Billing management isn't available yet.")
        return redirect("profile")
    profile = request.user.profile
    return_url = f"{settings.SITE_URL}{reverse('profile')}"
    try:
        session = stripe_utils.create_portal_session(profile, return_url)
    except Exception as exc:  # noqa: BLE001
        import logging
        logging.getLogger("billing").exception("portal session failed: %s", exc)
        messages.error(request, "We couldn't open billing just now. Please try again.")
        return redirect("profile")
    return redirect(session["url"], permanent=False)


# --- Webhook: the source of truth ----------------------------------------
def _ts_to_dt(ts):
    return datetime.fromtimestamp(ts, tz=dt_timezone.utc) if ts else None


def _period_end(sub):
    """Renewal date. In recent API versions (2025+) current_period_end moved from
    the subscription to its items, so read the item level first, then fall back."""
    items = (sub.get("items") or {}).get("data") or []
    pe = (items[0].get("current_period_end") if items else None) or sub.get("current_period_end")
    return _ts_to_dt(pe)


def _profile_for(customer_id=None, user_id=None):
    if user_id:
        p = Profile.objects.filter(user_id=user_id).first()
        if p:
            return p
    if customer_id:
        return Profile.objects.filter(stripe_customer_id=customer_id).first()
    return None


@csrf_exempt
@require_POST
def webhook(request):
    if not settings.STRIPE_WEBHOOK_SECRET:
        return HttpResponseBadRequest("webhook not configured")
    sig = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    try:
        event = stripe_utils.construct_event(request.body, sig)
    except Exception:  # noqa: BLE001 — bad signature / parse
        return HttpResponseBadRequest("invalid signature")

    etype = event["type"]
    event_id = event.get("id") or ""
    obj = event["data"]["object"]

    # Dedup: Stripe can deliver the same event more than once. Skip if already seen.
    if event_id and WebhookEvent.objects.filter(stripe_event_id=event_id).exists():
        return HttpResponse(status=200)

    if etype == "checkout.session.completed":
        profile = _profile_for(
            customer_id=obj.get("customer"),
            user_id=(obj.get("client_reference_id") or (obj.get("metadata") or {}).get("user_id")),
        )
        if profile:
            profile.stripe_customer_id = obj.get("customer") or profile.stripe_customer_id
            sub_id = obj.get("subscription")
            if sub_id:
                profile.stripe_subscription_id = sub_id
            profile.membership_status = Profile.MembershipStatus.ACTIVE
            # Fetch the subscription so the renewal date + price show immediately on the
            # profile (otherwise they populate a moment later via subscription.updated).
            if sub_id and stripe_utils.configured():
                try:
                    sub = stripe_utils.retrieve_subscription(sub_id)
                    profile.current_period_end = _period_end(sub)
                    items = (sub.get("items") or {}).get("data") or []
                    if items:
                        profile.price_id = (items[0].get("price") or {}).get("id", profile.price_id)
                except Exception:  # noqa: BLE001 — non-fatal; subscription.updated will fill these
                    import logging
                    logging.getLogger("billing").warning("could not fetch subscription %s", sub_id)
            profile.save()

    elif etype in ("customer.subscription.updated", "customer.subscription.created"):
        profile = _profile_for(customer_id=obj.get("customer"),
                               user_id=(obj.get("metadata") or {}).get("user_id"))
        if profile:
            status_map = {
                "active": Profile.MembershipStatus.ACTIVE,
                "trialing": Profile.MembershipStatus.ACTIVE,
                "past_due": Profile.MembershipStatus.PAST_DUE,
                "unpaid": Profile.MembershipStatus.PAST_DUE,
                "canceled": Profile.MembershipStatus.CANCELED,
                "incomplete": Profile.MembershipStatus.INCOMPLETE,
                "incomplete_expired": Profile.MembershipStatus.CANCELED,
            }
            profile.membership_status = status_map.get(obj.get("status"), profile.membership_status)
            profile.stripe_subscription_id = obj.get("id") or profile.stripe_subscription_id
            profile.current_period_end = _period_end(obj)
            items = (obj.get("items") or {}).get("data") or []
            if items:
                profile.price_id = (items[0].get("price") or {}).get("id", profile.price_id)
            profile.save()

    elif etype == "customer.subscription.deleted":
        profile = _profile_for(customer_id=obj.get("customer"))
        if profile:
            profile.membership_status = Profile.MembershipStatus.CANCELED
            profile.current_period_end = _period_end(obj)
            profile.save()

    elif etype == "invoice.payment_failed":
        profile = _profile_for(customer_id=obj.get("customer"))
        if profile:
            profile.membership_status = Profile.MembershipStatus.PAST_DUE
            profile.save()

    # Record the event (dedup + audit). Best-effort; never fail the webhook over the log.
    if event_id:
        try:
            WebhookEvent.objects.get_or_create(
                stripe_event_id=event_id, defaults={"type": etype}
            )
        except Exception:  # noqa: BLE001
            pass

    return HttpResponse(status=200)
