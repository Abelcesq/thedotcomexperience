from django.contrib import messages
from django.db.models import Q
from django.shortcuts import redirect, render

from .forms import DotApplicationForm, DotFinderForm, WaitlistForm
from .models import Dot


def home(request):
    """Simple landing inside the Django app (the marketing home stays on the Node site for now)."""
    return render(request, "dots/home.html")


def dots_finder(request):
    """Search Dots by city. If none, offer the waitlist or to request a new location."""
    form = DotFinderForm(request.GET or None)
    results = None
    query = ""
    if form.is_valid() and form.cleaned_data.get("city"):
        query = form.cleaned_data["city"].strip()
        results = Dot.objects.filter(
            Q(city__icontains=query) | Q(region__icontains=query)
        ).exclude(status=Dot.Status.PAUSED)

    waitlist_form = WaitlistForm(initial={"city": query} if query else None)
    return render(request, "dots/finder.html", {
        "form": form, "results": results, "query": query, "waitlist_form": waitlist_form,
    })


def waitlist_signup(request):
    if request.method != "POST":
        return redirect("dots_finder")
    form = WaitlistForm(request.POST)
    if form.is_valid():
        form.save()
        # (Optional) also forward to the Node /api/subscribe funnel — see billing/notify.py
        messages.success(request, "You're on the list. We'll be in touch about a Dot near you.")
    else:
        messages.error(request, "Please check the form and try again.")
    return redirect("dots_finder")


def request_dot(request):
    """Apply to charter and lead a new Dot (the vetted-ambassador application)."""
    if request.method == "POST":
        form = DotApplicationForm(request.POST)
        if form.is_valid():
            app = form.save(commit=False)
            if request.user.is_authenticated:
                app.user = request.user
            app.save()
            return render(request, "dots/request_done.html", {"application": app})
        messages.error(request, "Please check the form and try again.")
    else:
        initial = {}
        if request.user.is_authenticated:
            initial = {
                "full_name": request.user.get_full_name() or "",
                "email": request.user.email,
                "city": getattr(request.user.profile, "city", ""),
                "phone": getattr(request.user.profile, "phone", ""),
            }
        form = DotApplicationForm(initial=initial)
    return render(request, "dots/request.html", {"form": form})
