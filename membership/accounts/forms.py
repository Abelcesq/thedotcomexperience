import phonenumbers
from allauth.account.forms import LoginForm, SignupForm
from django import forms
from django.utils import timezone

from thedotx import captcha
from thedotx.captcha import CaptchaFormMixin

from .countries import COUNTRIES, PREFERRED
from .models import Profile


def _country_choices():
    """Preferred countries first, then everyone alphabetically. Label: "Mexico (+52)"."""
    by_iso = {iso: (name, dial) for iso, name, dial in COUNTRIES}
    label = lambda iso: f"{by_iso[iso][0]} (+{by_iso[iso][1]})"
    top = [(iso, label(iso)) for iso in PREFERRED]
    rest = [(iso, label(iso)) for iso, _n, _d in COUNTRIES if iso not in PREFERRED]
    return top + rest


COC_LABEL = (
    'I have read and agree to the '
    '<a href="https://www.thedotx.com/terms" target="_blank" rel="noopener">Terms</a> and the '
    '<a href="https://www.thedotx.com/terms#conduct" target="_blank" rel="noopener">Code of Conduct</a>, '
    "including that membership fees are forfeited if I am removed for a violation."
)


class DotxLoginForm(LoginForm):
    """The sign-in form, with the "I'm not a robot" checkbox when reCAPTCHA is configured."""

    captcha_action = "login"

    def clean(self):
        # Check the box BEFORE looking at the password, so a script cannot use this page
        # to test stolen passwords without solving the check each time.
        if captcha.enabled() and not captcha.passes(self.data.get(captcha.FIELD, ""), self.captcha_action):
            self.add_error(None, captcha.MESSAGE)
        return super().clean()


class DotxSignupForm(CaptchaFormMixin, SignupForm):
    """allauth signup + first name and the required Code of Conduct agreement."""

    captcha_action = "signup"

    first_name = forms.CharField(
        max_length=60, required=False, label="First name",
        widget=forms.TextInput(attrs={"placeholder": "First name"}),
    )
    coc_agreed = forms.BooleanField(
        required=True, label=COC_LABEL,
        error_messages={"required": "You must agree to the Code of Conduct to join."},
    )

    field_order = ["first_name", "email", "password1", "password2", "coc_agreed"]

    def save(self, request):
        user = super().save(request)
        first = self.cleaned_data.get("first_name", "").strip()
        if first:
            user.first_name = first
            user.save(update_fields=["first_name"])
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.display_name = first or profile.display_name
        profile.coc_agreed = True
        profile.coc_agreed_at = timezone.now()
        profile.save()
        return user


class ProfileForm(forms.ModelForm):
    """Member profile details: display name, city, bio, phone (country code + number), SMS consent.

    The phone is entered as a country dialing code plus a local number and stored as one
    international (E.164) number, e.g. +19165550123.
    """

    phone_country = forms.ChoiceField(
        label="Country", required=False, choices=_country_choices, initial="US",
        widget=forms.Select(attrs={"autocomplete": "tel-country-code", "aria-label": "Country code"}),
    )
    phone_number = forms.CharField(
        label="Phone", required=False, max_length=32,
        widget=forms.TextInput(attrs={"placeholder": "Your phone number", "type": "tel",
                                      "inputmode": "tel", "autocomplete": "tel-national"}),
    )

    class Meta:
        model = Profile
        fields = ["display_name", "city", "bio", "directory_visible", "sms_opt_in"]
        labels = {
            "display_name": "Display name",
            "city": "City",
            "bio": "About you",
            "directory_visible": "Show me in the member directory",
            "sms_opt_in": "Text me a reminder before my Dot meets",
        }
        help_texts = {
            "display_name": "The name other members see.",
            "city": "Used to match you to a local Dot. Shown on your member page.",
            "bio": "A line or two other members will see on your page (300 characters).",
            "directory_visible": "Other members can find your page, see your name, city and tier, and ask "
                                 "to connect. Your email and phone are never shown. Turn this off to stay private.",
            "sms_opt_in": "About one text a week from The Dot Com Experience, sent before your Dot meets. "
                          "Message and data rates may apply. Reply STOP to cancel or HELP for help. "
                          "Texts are optional and never a condition of membership.",
        }
        widgets = {
            "city": forms.TextInput(attrs={"placeholder": "e.g. Los Angeles"}),
            "bio": forms.Textarea(attrs={"rows": 3, "maxlength": 300,
                                         "placeholder": "What brought you here?"}),
        }

    field_order = ["display_name", "city", "bio", "directory_visible",
                   "phone_country", "phone_number", "sms_opt_in"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remembered so save() can tell when someone newly agrees to texts.
        self._was_opted_in = bool(self.instance.pk and self.instance.sms_opt_in)
        self._old_phone = self.instance.phone if self.instance.pk else ""
        self.newly_opted_in = False
        # Show a saved number split back into its country and local parts.
        stored = self.instance.phone if self.instance and self.instance.pk else ""
        if stored:
            try:
                parsed = phonenumbers.parse(stored, None)
                region = phonenumbers.region_code_for_number(parsed)
                if region:
                    self.fields["phone_country"].initial = region
                self.fields["phone_number"].initial = phonenumbers.format_number(
                    parsed, phonenumbers.PhoneNumberFormat.NATIONAL)
            except phonenumbers.NumberParseException:
                self.fields["phone_number"].initial = stored

    def clean(self):
        cleaned = super().clean()
        raw = (cleaned.get("phone_number") or "").strip()
        country = cleaned.get("phone_country") or "US"
        phone = ""
        if raw:
            try:
                parsed = phonenumbers.parse(raw, country)
            except phonenumbers.NumberParseException:
                parsed = None
            if parsed is None or not phonenumbers.is_possible_number(parsed):
                self.add_error("phone_number",
                               "That doesn't look like a complete phone number for the country selected.")
            else:
                phone = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        cleaned["phone"] = phone
        if cleaned.get("sms_opt_in") and not phone and "phone_number" not in self.errors:
            self.add_error("phone_number", "Add a phone number to receive texts about your Dot.")
        return cleaned

    def save(self, commit=True):
        profile = self.instance
        profile.phone = self.cleaned_data.get("phone", "")
        if profile.sms_opt_in:
            # New consent, or consent given for a different number: record when.
            if not self._was_opted_in or profile.phone != self._old_phone:
                profile.sms_opt_in_at = timezone.now()
                self.newly_opted_in = True
        else:
            profile.sms_opt_in_at = None
        return super().save(commit=commit)
