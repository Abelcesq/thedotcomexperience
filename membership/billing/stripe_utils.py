"""Thin helpers around the Stripe SDK. All calls are no-ops if Stripe isn't configured."""
from django.conf import settings
import stripe


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
    """Hosted Checkout for the $20/mo subscription (PCI stays with Stripe)."""
    s = _client()
    customer_id = ensure_customer(profile)
    return s.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        client_reference_id=str(profile.user_id),
        line_items=[{"price": settings.STRIPE_PRICE_ID, "quantity": 1}],
        allow_promotion_codes=settings.STRIPE_ALLOW_PROMOTION_CODES,
        success_url=success_url,
        cancel_url=cancel_url,
        subscription_data={"metadata": {"user_id": str(profile.user_id)}},
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
