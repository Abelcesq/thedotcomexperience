"""Thin helpers around the Stripe SDK. All calls are no-ops if Stripe isn't configured."""
from datetime import datetime, timezone

from django.conf import settings
import stripe


def _first_of_next_month_ts(now=None):
    """Unix timestamp for 12:00 UTC on the 1st of next month.

    Noon UTC keeps the billing date on the 1st across all US time zones
    (and most of the world), so members see the charge land on the 1st.
    """
    now = now or datetime.now(timezone.utc)
    year, month = now.year, now.month
    if month == 12:
        year, month = year + 1, 1
    else:
        month += 1
    anchor = datetime(year, month, 1, 12, 0, 0, tzinfo=timezone.utc)
    return int(anchor.timestamp())


def configured():
    return bool(settings.STRIPE_SECRET_KEY and settings.STRIPE_PRICE_ID)


def _client():
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def ensure_customer(profile):
    """Return a Stripe customer id for the member, creating one if needed."""
    if profile.stripe_customer_id:
        return profile.stripe_customer_id
    s = _client()
    customer = s.Customer.create(
        email=profile.user.email,
        name=profile.display_name or profile.user.get_full_name() or "",
        metadata={"user_id": str(profile.user_id)},
    )
    profile.stripe_customer_id = customer["id"]
    profile.save(update_fields=["stripe_customer_id"])
    return customer["id"]


def create_checkout_session(profile, success_url, cancel_url):
    """Hosted Checkout for the $100/mo subscription (PCI stays with Stripe).

    Every member is aligned to bill on the 1st of the month. For anyone who
    joins mid-month, the new subscription's billing cycle is anchored to the
    1st of next month and Stripe prorates the partial first month (charged at
    checkout); the full $100 is then billed on the 1st every month after.
    Members who happen to join on the 1st pay the full $100 now and are already
    on a 1st-of-month cycle, so no anchor is needed.
    """
    s = _client()
    customer_id = ensure_customer(profile)
    sub_data = {"metadata": {"user_id": str(profile.user_id)}}
    now = datetime.now(timezone.utc)
    if now.day != 1:
        sub_data["billing_cycle_anchor"] = _first_of_next_month_ts(now)
        sub_data["proration_behavior"] = "create_prorations"
    return s.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        client_reference_id=str(profile.user_id),
        line_items=[{"price": settings.STRIPE_PRICE_ID, "quantity": 1}],
        allow_promotion_codes=settings.STRIPE_ALLOW_PROMOTION_CODES,
        success_url=success_url,
        cancel_url=cancel_url,
        subscription_data=sub_data,
    )


def create_portal_session(profile, return_url):
    """Stripe Customer Portal: update card, view invoices, cancel — no custom UI."""
    s = _client()
    customer_id = ensure_customer(profile)
    return s.billing_portal.Session.create(customer=customer_id, return_url=return_url)


def retrieve_subscription(subscription_id):
    """Fetch a subscription (for the renewal date right after checkout)."""
    s = _client()
    return s.Subscription.retrieve(subscription_id)


def construct_event(payload, sig_header):
    """Verify + parse a webhook. Raises on bad signature."""
    return stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
