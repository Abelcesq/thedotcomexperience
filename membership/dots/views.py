from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, render

from .forms import DotApplicationForm, DotFinderForm, WaitlistForm
from .models import Dot


def _dots_with_coords():
    """Every Dot that has coordinates and isn't paused — the markers for the maps."""
    out = []
    qs = Dot.objects.exclude(lat__isnull=True).exclude(lng__isnull=True).exclude(status=Dot.Status.PAUSED)
    for d in qs:
        label = d.city + (", " + d.region if d.region else "")
        out.append({
            "city": label, "lat": d.lat, "lng": d.lng,
            "status": d.get_status_display(), "count": 1,
        })
    return out


def dots_data(request):
    """Public JSON of current Dots, for the interactive maps (home page fetches it
    cross-origin; the members finder renders it server-side). Read-only, no secrets."""
    resp = JsonResponse({"dots": _dots_with_coords()})
    resp["Access-Control-Allow-Origin"] = "*"   # public, read-only data
    resp["Cache-Control"] = "public, max-age=120"
    return resp


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

    # Markers for the interactive map: every Dot that has coordinates.
    map_dots = _dots_with_coords()

    waitlist_form = WaitlistForm(initial={"city": query} if query else None)
    return render(request, "dots/finder.html", {
        "form": form, "results": results, "query": query,
        "waitlist_form": waitlist_form, "map_dots": map_dots,
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
