"""Who may see and contact whom."""
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from .models import Block, Connection


def member_required(view):
    """Signed in, and an active member, a Charter holder, or staff."""

    @wraps(view)
    @login_required
    def wrapped(request, *args, **kwargs):
        if not request.user.profile.can_use_community:
            messages.info(request, "The member community opens once your membership is active.")
            return redirect("join")
        return view(request, *args, **kwargs)

    return wrapped


def is_connected(a, b):
    c = Connection.between(a, b)
    return bool(c and c.status == Connection.Status.ACCEPTED)


def in_same_line(a, b):
    """True when one directly reports to the other (e.g. a Member and their Ambassador)."""
    pa, pb = a.profile, b.profile
    return pa.reports_to_id == pb.pk or pb.reports_to_id == pa.pk


def can_view_profile(viewer, target):
    if viewer.id == target.id or viewer.is_staff:
        return True
    if Block.exists_between(viewer, target):
        return False
    if not target.profile.can_use_community:
        return False
    if target.profile.directory_visible:
        return True
    # Hidden from the directory: still visible to people already linked to them.
    return is_connected(viewer, target) or in_same_line(viewer, target)


def can_message(sender, recipient):
    """Messages are for connected members, a direct upline/downline pair, or staff."""
    if sender.id == recipient.id:
        return False
    if Block.exists_between(sender, recipient):
        return False
    if sender.is_staff or recipient.is_staff:
        return True
    if not recipient.profile.can_use_community:
        return False
    return is_connected(sender, recipient) or in_same_line(sender, recipient)
