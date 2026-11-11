import re

from allauth.account.forms import SignupForm
from django import forms
from django.utils import timezone

from .models import Profile


COC_LABEL = (
    'I have read and agree to the '
    '<a href="https://www.thedotx.com/terms" target="_blank" rel="noopener">Terms</a> and the '
    '<a href="https://www.thedotx.com/terms#conduct" target="_blank" rel="noopener">Code of Conduct</a>, '
    "including that membership fees are forfeited if I am removed for a violation."
)


class DotxSignupForm(SignupForm):
    """allauth signup + first name and the required Code of Conduct agreement."""

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
    """Member profile details: display name, city, phone + SMS consent."""

    class Meta:
        model = Profile
        fields = ["display_name", "city", "bio", "directory_visible", "phone", "sms_opt_in"]
        labels = {
            "display_name": "Display name",
            "city": "City",
            "bio": "About you",
            "directory_visible": "Show me in the member directory",
            "phone": "Phone number",
            "sms_opt_in": "Text me about my Dot",
        }
        help_texts = {
            "display_name": "The name other members see.",
            "city": "Used to match you to a local Dot. Shown on your member page.",
            "bio": "A line or two other members will see on your page (300 characters).",
            "directory_visible": "Other members can find your page, see your name, city and tier, and ask "
                                 "to connect. Your email and phone are never shown. Turn this off to stay private.",
            "phone": "Optional. Pick your country, then enter your number — we store it in international format.",
            "sms_opt_in": "We only text if you opt in, and you can reply STOP anytime.",
        }
        widgets = {
            "phone": forms.TextInput(attrs={"placeholder": "Phone number", "type": "tel",
                                            "autocomplete": "tel"}),
            "city": forms.TextInput(attrs={"placeholder": "e.g. Los Angeles"}),
            "bio": forms.Textarea(attrs={"rows": 3, "maxlength": 300,
                                         "placeholder": "What brought you here?"}),
        }

    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").strip()
        if not phone:
            return phone
        # The country picker submits E.164 (+<country><number>). Strip any stray
        # formatting (spaces, parens, dashes) just in case, then validate.
        cleaned = re.sub(r"[\s()\-.]", "", phone)
        if not re.fullmatch(r"\+\d{8,15}", cleaned):
            raise forms.ValidationError(
                "Enter a valid phone number in international format, e.g. +13105551234."
            )
        return cleaned

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("sms_opt_in") and not cleaned.get("phone"):
            self.add_error("phone", "Add a phone number to receive texts about your Dot.")
        return cleaned
