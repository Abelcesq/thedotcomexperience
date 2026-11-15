from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from dots.models import Dot, DotMembership
from . import photos
from .forms import ProfileForm
from .models import Profile, ProfilePhoto


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
        form = ProfileForm(request.POST, request.FILES, instance=profile)
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


@login_required
@require_POST
def profile_photo(request):
    """Add, replace or remove the signed-in member's own profile photo."""
    profile = request.user.profile
    if request.POST.get("remove"):
        photos.remove_photo(profile)
        messages.success(request, "Your photo has been removed.")
    else:
        try:
            photos.set_photo(profile, request.FILES.get("photo"))
            messages.success(request, "Your photo has been updated.")
        except photos.PhotoError as problem:
            messages.error(request, str(problem))
    go = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(go, allowed_hosts={request.get_host()},
                                           require_https=request.is_secure()):
        go = "profile"
    return redirect(go)


@login_required
@require_GET
def member_photo(request, member_id):
    """Serve a member's photo to people allowed to see that member's page."""
    from community.access import can_view_profile

    target = get_object_or_404(Profile.objects.select_related("user"), member_id=member_id)
    me = request.user
    if target.user_id != me.id:
        if not (me.is_staff or me.profile.can_use_community) or not can_view_profile(me, target.user):
            raise Http404("No photo.")
    try:
        data = bytes(target.photo.image)
    except ProfilePhoto.DoesNotExist:
        raise Http404("No photo.")
    response = HttpResponse(data, content_type="image/jpeg")
    # The address changes whenever the photo does, so the browser may keep its copy.
    response["Cache-Control"] = "private, max-age=31536000, immutable"
    response["X-Content-Type-Options"] = "nosniff"
    return response
