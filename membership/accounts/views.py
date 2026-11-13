from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from dots.models import Dot, DotMembership
from .forms import ProfileForm


@login_required
def profile(request):
    profile = request.user.profile

    # The Stripe success redirect lands here with ?stripe=ok — reassure, webhook confirms.
    stripe_pending = request.GET.get("stripe") == "ok"

    # My Dot (if any) — membership in a Dot, else None.
    dot_membership = (
        DotMembership.objects.select_related("dot").filter(user=request.user).first()
    )

    # Account security: is the email confirmed, and is two-step verification switched on?
    from allauth.account.models import EmailAddress
    from allauth.mfa.models import Authenticator
    email_verified = EmailAddress.objects.filter(user=request.user, verified=True).exists()
    two_step_on = Authenticator.objects.filter(
        user=request.user, type=Authenticator.Type.TOTP).exists()

    context = {
        "email_verified": email_verified,
        "two_step_on": two_step_on,
        "profile": profile,
        "stripe_pending": stripe_pending,
        "dot_membership": dot_membership,
    }
    return render(request, "account/profile.html", context)


@login_required
def profile_edit(request):
    profile = request.user.profile
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            saved = form.save()
            if form.newly_opted_in:
                # A one-time "you're signed up" text (does nothing until texting is switched on).
                from sms.reminders import send_confirmation
                send_confirmation(saved)
            messages.success(request, "Your profile has been updated.")
            return redirect("profile")
    else:
        form = ProfileForm(instance=profile)
    return render(request, "account/profile_edit.html", {"form": form, "profile": profile})
