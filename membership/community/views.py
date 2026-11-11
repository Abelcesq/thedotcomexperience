"""Member directory, profiles, connections, private messages, and the "My team" view."""
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Max, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts.models import Profile
from .access import can_message, can_view_profile, in_same_line, is_connected, member_required
from .models import Block, Connection, Message, Report

TIER_FILTERS = [
    (Profile.Role.MEMBER, "Members"),
    (Profile.Role.AMBASSADOR, "Ambassadors"),
    (Profile.Role.LOCAL_LEADER, "Local Leaders"),
    (Profile.Role.REGIONAL, "Regionals"),
]


def _in_community():
    """Profiles that belong in the community: active members and Charter holders."""
    return Q(membership_status=Profile.MembershipStatus.ACTIVE) | Q(
        role__in=[Profile.Role.AMBASSADOR, Profile.Role.LOCAL_LEADER, Profile.Role.REGIONAL])


def _blocked_user_ids(user):
    ids = set(Block.objects.filter(blocker=user).values_list("blocked_id", flat=True))
    ids |= set(Block.objects.filter(blocked=user).values_list("blocker_id", flat=True))
    return ids


def _back(request, default):
    """Where to send the member after an action: a safe, same-site ?next, else the default."""
    nxt = request.POST.get("next") or ""
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()},
                                               require_https=request.is_secure()):
        return redirect(nxt)
    return redirect(default)


def _target(member_id):
    return get_object_or_404(Profile.objects.select_related("user", "reports_to__user"),
                             member_id=member_id.upper())


# --- Directory --------------------------------------------------------------
@member_required
def directory(request):
    q = (request.GET.get("q") or "").strip()
    tier = request.GET.get("tier") or ""
    people = (Profile.objects.select_related("user")
              .filter(_in_community(), directory_visible=True)
              .exclude(user_id__in=_blocked_user_ids(request.user)))
    if q:
        people = people.filter(
            Q(display_name__icontains=q) | Q(user__first_name__icontains=q)
            | Q(user__last_name__icontains=q) | Q(city__icontains=q)
            | Q(member_id__iexact=q))
    if tier in dict(TIER_FILTERS):
        people = people.filter(role=tier)
    people = people.order_by("display_name", "member_id")
    page = Paginator(people, 24).get_page(request.GET.get("page"))
    return render(request, "community/directory.html", {
        "page": page, "q": q, "tier": tier, "tier_filters": TIER_FILTERS,
        "total": people.count(),
    })


# --- A member's profile -------------------------------------------------------
@member_required
def member_profile(request, member_id):
    target = _target(member_id)
    me = request.user
    if not can_view_profile(me, target.user):
        raise Http404("Member not found.")
    is_self = target.user_id == me.id
    connection = None if is_self else Connection.between(me, target.user)
    state = "none"
    if is_self:
        state = "self"
    elif connection and connection.status == Connection.Status.ACCEPTED:
        state = "connected"
    elif connection and connection.requester_id == me.id:
        state = "requested"
    elif connection:
        state = "incoming"
    return render(request, "community/profile.html", {
        "target": target,
        "state": state,
        "can_message": (not is_self) and can_message(me, target.user),
        "same_line": (not is_self) and in_same_line(me, target.user),
        "connection_count": Connection.accepted_for(target.user).count(),
        "stats": target.team_stats() if target.is_charter_holder else None,
        "i_blocked": Block.objects.filter(blocker=me, blocked=target.user).exists(),
    })


# --- Connections ----------------------------------------------------------------
@member_required
def connections(request):
    me = request.user
    accepted = [c.other(me).profile for c in
                Connection.accepted_for(me).select_related("requester__profile", "addressee__profile")]
    incoming = Connection.objects.filter(
        addressee=me, status=Connection.Status.PENDING).select_related("requester__profile")
    outgoing = Connection.objects.filter(
        requester=me, status=Connection.Status.PENDING).select_related("addressee__profile")
    return render(request, "community/connections.html", {
        "accepted": sorted(accepted, key=lambda p: p.name.lower()),
        "incoming": incoming, "outgoing": outgoing,
    })


@require_POST
@member_required
def connect(request, member_id):
    target = _target(member_id)
    me = request.user
    if target.user_id == me.id or not can_view_profile(me, target.user):
        raise Http404
    existing = Connection.between(me, target.user)
    if existing:
        # They already asked me: treat my request as accepting theirs.
        if existing.status == Connection.Status.PENDING and existing.addressee_id == me.id:
            existing.status = Connection.Status.ACCEPTED
            existing.responded_at = timezone.now()
            existing.save()
            messages.success(request, f"You're now connected with {target.name}.")
        return redirect("member_profile", member_id=target.member_id)
    since = timezone.now() - timedelta(days=1)
    sent_today = Connection.objects.filter(requester=me, created_at__gte=since).count()
    if sent_today >= settings.COMMUNITY_MAX_REQUESTS_PER_DAY and not me.is_staff:
        messages.error(request, "You've reached today's limit for connection requests. Try again tomorrow.")
        return redirect("member_profile", member_id=target.member_id)
    Connection.objects.create(requester=me, addressee=target.user)
    messages.success(request, f"Connection request sent to {target.name}.")
    return redirect("member_profile", member_id=target.member_id)


@require_POST
@member_required
def respond(request, member_id, action):
    """Accept or decline a request that this member received."""
    target = _target(member_id)
    conn = get_object_or_404(Connection, requester=target.user, addressee=request.user,
                             status=Connection.Status.PENDING)
    if action == "accept":
        conn.status = Connection.Status.ACCEPTED
        conn.responded_at = timezone.now()
        conn.save()
        messages.success(request, f"You're now connected with {target.name}.")
    else:
        conn.delete()
        messages.info(request, "Request declined.")
    return _back(request, "connections")


@require_POST
@member_required
def disconnect(request, member_id):
    """Remove a connection, or withdraw a request I sent."""
    target = _target(member_id)
    conn = Connection.between(request.user, target.user)
    if conn:
        conn.delete()
        messages.info(request, f"You're no longer connected with {target.name}.")
    return _back(request, "connections")


# --- Safety: block and report ---------------------------------------------------
@require_POST
@member_required
def block(request, member_id):
    target = _target(member_id)
    me = request.user
    if target.user_id == me.id:
        raise Http404
    Block.objects.get_or_create(blocker=me, blocked=target.user)
    conn = Connection.between(me, target.user)
    if conn:
        conn.delete()
    messages.info(request, f"You've blocked {target.name}. They can no longer see your profile or message you.")
    return redirect("member_directory")


@require_POST
@member_required
def unblock(request, member_id):
    target = _target(member_id)
    Block.objects.filter(blocker=request.user, blocked=target.user).delete()
    messages.info(request, f"You've unblocked {target.name}.")
    return redirect("member_profile", member_id=target.member_id)


@require_POST
@member_required
def report(request, member_id):
    target = _target(member_id)
    me = request.user
    reason = (request.POST.get("reason") or "").strip()[:1000]
    if target.user_id == me.id:
        raise Http404
    if not reason:
        messages.error(request, "Please tell us what happened so we can review it.")
        return redirect("member_profile", member_id=target.member_id)
    recent = list(Message.thread(me, target.user).order_by("-created_at")[:30])[::-1]
    snapshot = "\n".join(
        f"[{m.created_at:%Y-%m-%d %H:%M} UTC] {m.sender.profile.member_id}: {m.body}" for m in recent)
    Report.objects.create(reporter=me, reported=target.user, reason=reason,
                          conversation_snapshot=snapshot)
    messages.success(request, "Thank you — your report was sent to our team for review. "
                              "You can also block this member at any time.")
    return redirect("member_directory")


# --- Messages -----------------------------------------------------------------------
@member_required
def inbox(request):
    me = request.user
    blocked = _blocked_user_ids(me)
    latest = {}
    sent = (Message.objects.filter(sender=me).values("recipient")
            .annotate(last=Max("created_at")))
    received = (Message.objects.filter(recipient=me).values("sender")
                .annotate(last=Max("created_at")))
    for row in sent:
        latest[row["recipient"]] = row["last"]
    for row in received:
        uid = row["sender"]
        latest[uid] = max(latest.get(uid, row["last"]), row["last"])
    profiles = {p.user_id: p for p in
                Profile.objects.select_related("user").filter(user_id__in=latest.keys())}
    conversations = []
    for uid, when in sorted(latest.items(), key=lambda kv: kv[1], reverse=True):
        if uid in blocked or uid not in profiles:
            continue
        last = Message.thread(me, profiles[uid].user).order_by("-created_at").first()
        conversations.append({
            "profile": profiles[uid], "last": last,
            "unread": Message.objects.filter(sender_id=uid, recipient=me, read_at__isnull=True).count(),
        })
    return render(request, "community/inbox.html", {"conversations": conversations})


@member_required
def thread(request, member_id):
    target = _target(member_id)
    me = request.user
    if target.user_id == me.id:
        return redirect("member_inbox")
    allowed = can_message(me, target.user)
    history = Message.thread(me, target.user)
    if not allowed and not history.exists():
        messages.info(request, f"Connect with {target.name} to send a message.")
        return redirect("member_profile", member_id=target.member_id)

    if request.method == "POST":
        body = (request.POST.get("body") or "").strip()
        if not allowed:
            messages.error(request, "You can't message this member.")
        elif not body:
            messages.error(request, "Write a message first.")
        elif len(body) > settings.COMMUNITY_MESSAGE_MAX_LENGTH:
            messages.error(request, f"Messages are limited to {settings.COMMUNITY_MESSAGE_MAX_LENGTH} characters.")
        else:
            window = timezone.now() - timedelta(minutes=5)
            recent = Message.objects.filter(sender=me, created_at__gte=window).count()
            if recent >= settings.COMMUNITY_MAX_MESSAGES_PER_5_MIN and not me.is_staff:
                messages.error(request, "You're sending messages very quickly. Please wait a few minutes.")
            else:
                Message.objects.create(sender=me, recipient=target.user, body=body)
        return redirect("member_thread", member_id=target.member_id)

    Message.objects.filter(sender=target.user, recipient=me, read_at__isnull=True).update(
        read_at=timezone.now())
    return render(request, "community/thread.html", {
        "target": target, "thread": history, "allowed": allowed,
        "max_length": settings.COMMUNITY_MESSAGE_MAX_LENGTH,
    })


# --- My team (Charter holders) ----------------------------------------------------------
@member_required
def my_team(request):
    me = request.user.profile
    if not me.is_charter_holder:
        messages.info(request, "The team view is for Ambassadors, Local Leaders, and Regionals.")
        return redirect("profile")
    people = []
    for person in me.direct_reports().order_by("display_name", "member_id"):
        people.append({"profile": person,
                       "stats": person.team_stats() if person.is_charter_holder else None})
    return render(request, "community/team.html", {
        "me": me, "stats": me.team_stats(), "people": people,
    })
