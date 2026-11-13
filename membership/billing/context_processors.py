from django.conf import settings


def membership_flags(request):
    """Expose membership/Stripe display values to all templates."""
    profile = None
    if request.user.is_authenticated:
        profile = getattr(request.user, "profile", None)
    return {
        "MEMBERSHIP_PRICE_LABEL": settings.MEMBERSHIP_PRICE_LABEL,
        "STRIPE_CONFIGURED": bool(settings.STRIPE_SECRET_KEY and settings.STRIPE_PRICE_ID),
        "my_profile": profile,
        # Only handed to templates when the captcha is switched on (secret key present).
        "RECAPTCHA_SITE_KEY": settings.RECAPTCHA_SITE_KEY if settings.RECAPTCHA_SECRET_KEY else "",
    }
