"""Deciding who gets a Dot reminder, when, and what it says."""
from django.conf import settings
from django.utils import timezone

from accounts.models import Profile
from dots.models import Dot
from dots.schedule import reminder_time
from . import service
from .models import SmsLog

STOP_LINE = "Reply STOP to opt out."


def _clock(start):
    return start.strftime("%I:%M %p").lstrip("0")        # "7:00 PM"


def reminder_text(dot, start, sent_on):
    when = "today" if sent_on == start.date() else "tomorrow"
    base = f"{settings.SMS_BRAND}: {dot.name} meets {when} at {_clock(start)}"
    with_place = f"{base} at {dot.location}. {STOP_LINE}" if dot.location else ""
    # Keep to one standard text (160 characters); drop the address if it doesn't fit.
    return with_place if with_place and len(with_place) <= 160 else f"{base}. {STOP_LINE}"


def confirmation_text():
    return (f"{settings.SMS_BRAND}: You're signed up for Dot reminders, about 1 msg/week. "
            "Msg & data rates may apply. Reply HELP for help, STOP to opt out.")


def test_text():
    return f"{settings.SMS_BRAND}: This is a test message. {STOP_LINE}"


def recipients(dot):
    """Seated members of the Dot plus its Ambassador, who opted in and are in good standing."""
    user_ids = set(dot.memberships.values_list("user_id", flat=True))
    if dot.ambassador_id:
        user_ids.add(dot.ambassador_id)
    people = Profile.objects.select_related("user").filter(
        user_id__in=user_ids, sms_opt_in=True).exclude(phone="")
    return [p for p in people if p.can_use_community]


def due(now=None):
    """(dot, meeting start) for every Dot whose reminder time has arrived and hasn't yet met."""
    now = now or timezone.now()
    out = []
    for dot in Dot.objects.exclude(status=Dot.Status.PAUSED):
        start = dot.next_meeting(now)
        if not start:
            continue
        send_at = reminder_time(start, settings.SMS_REMINDER_HOURS_BEFORE,
                                settings.SMS_QUIET_START_HOUR, settings.SMS_QUIET_END_HOUR)
        if send_at <= now < start:
            out.append((dot, start))
    return out


def send_due(now=None, dry_run=False):
    """Send every reminder that is due. Safe to run as often as you like."""
    now = now or timezone.now()
    report = []
    for dot, start in due(now):
        sent_on = now.astimezone(start.tzinfo).date()
        body = reminder_text(dot, start, sent_on)
        for profile in recipients(dot):
            if dry_run:
                already = SmsLog.objects.filter(user=profile.user, dot=dot, kind="reminder",
                                                meeting_date=start.date()).exists()
                report.append((dot, profile, "already sent" if already else "would send", body))
                continue
            entry = service.send(profile, body, SmsLog.Kind.REMINDER, dot=dot,
                                 meeting_date=start.date())
            if entry:
                report.append((dot, profile, entry.status, body))
    return report


def send_confirmation(profile):
    return service.send(profile, confirmation_text(), SmsLog.Kind.CONFIRMATION)


def send_test(profile):
    return service.send(profile, test_text(), SmsLog.Kind.TEST)
