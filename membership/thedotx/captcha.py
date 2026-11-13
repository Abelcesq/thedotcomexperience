"""Google reCAPTCHA v3 for the public forms. Invisible to visitors; off until the secret key is set."""
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from django import forms
from django.conf import settings

log = logging.getLogger(__name__)
FIELD = "g-recaptcha-response"           # the hidden field the page fills in before submitting
MESSAGE = ("We couldn’t confirm you’re not a robot. Please try again — if you use an ad or "
           "tracker blocker, switch it off for this page.")


def enabled():
    return bool(settings.RECAPTCHA_SITE_KEY and settings.RECAPTCHA_SECRET_KEY)


def _ask_google(token):
    """One API call to Google. Kept separate so tests can replace it. Returns Google's reply."""
    data = urllib.parse.urlencode({"secret": settings.RECAPTCHA_SECRET_KEY, "response": token}).encode()
    request = urllib.request.Request("https://www.google.com/recaptcha/api/siteverify", data=data)
    with urllib.request.urlopen(request, timeout=8) as response:
        return json.load(response)


def passes(token, action=None):
    """True if Google says the visitor looks human (score at or above RECAPTCHA_MIN_SCORE).

    If Google can't be reached we let the visitor through (the other protections still
    apply) rather than lock every real person out.
    """
    if not token:
        return False
    try:
        reply = _ask_google(token)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        log.error("Could not reach Google reCAPTCHA: %s", exc)
        return True
    if not reply.get("success"):
        return False
    score = reply.get("score")
    if isinstance(score, (int, float)) and score < settings.RECAPTCHA_MIN_SCORE:
        return False
    if action and reply.get("action") and reply["action"] != action:
        return False                      # a token made for a different form
    return True


class CaptchaFormMixin:
    """Add to a form to require the reCAPTCHA check whenever the secret key is configured."""

    captcha_action = None                 # set on the form to tie tokens to it, e.g. "signup"

    def clean(self):
        cleaned = super().clean()
        if enabled() and not passes(self.data.get(FIELD, ""), self.captcha_action):
            raise forms.ValidationError(MESSAGE)
        return cleaned


class BotTrapMixin:
    """A field people never see. If it comes back filled, a script submitted the form."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["website"] = forms.CharField(
            required=False, label="",
            widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off",
                                          "style": "position:absolute;left:-9999px;width:1px;height:1px",
                                          "aria-hidden": "true"}))

    @property
    def is_bot(self):
        return bool((self.cleaned_data or {}).get("website"))
