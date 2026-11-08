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

    context = {
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
            form.save()
            messages.success(request, "Your profile has been updated.")
            return redirect("profile")
    else:
        form = ProfileForm(instance=profile)
    return render(request, "account/profile_edit.html", {"form": form, "profile": profile})
