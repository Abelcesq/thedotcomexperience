from django import forms

from thedotx.captcha import BotTrapMixin, CaptchaFormMixin

from .models import DotApplication, Waitlist


class DotFinderForm(forms.Form):
    city = forms.CharField(
        max_length=120, required=False, label="Your city or ZIP",
        widget=forms.TextInput(attrs={"placeholder": "e.g. Los Angeles"}),
    )


class WaitlistForm(BotTrapMixin, CaptchaFormMixin, forms.ModelForm):
    captcha_action = "waitlist"

    class Meta:
        model = Waitlist
        fields = ["first_name", "email", "city", "intent"]
        widgets = {
            "intent": forms.RadioSelect,
            "first_name": forms.TextInput(attrs={"placeholder": "First name"}),
            "email": forms.EmailInput(attrs={"placeholder": "you@example.com"}),
            "city": forms.TextInput(attrs={"placeholder": "e.g. Los Angeles"}),
        }


class DotApplicationForm(BotTrapMixin, CaptchaFormMixin, forms.ModelForm):
    captcha_action = "dot_request"

    agree = forms.BooleanField(
        required=True,
        label="I understand chartering a Dot is an application and training process, "
              "and that I must run it to the movement's standards.",
    )

    class Meta:
        model = DotApplication
        fields = ["full_name", "email", "phone", "city", "why"]
        widgets = {
            "why": forms.Textarea(attrs={"rows": 4,
                 "placeholder": "Tell us why you want to bring a Dot to your city."}),
        }
