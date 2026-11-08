from allauth.account.adapter import DefaultAccountAdapter


class DotxAccountAdapter(DefaultAccountAdapter):
    """Lightweight adapter hook point (branding, future email customization)."""

    def get_login_redirect_url(self, request):
        return "/accounts/profile/"
