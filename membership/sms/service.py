"""Sending text messages through Twilio. With no Twilio settings, nothing is ever sent."""
import base64
import hashlib
import hmac
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from django.conf import settings
from django.db import IntegrityError, transaction

from .models import SmsLog

log = logging.getLogger(__name__)

# Twilio's "this person has opted out" error: stop texting them and record it.
TWILIO_OPTED_OUT = 21610


@dataclass
class Result:
    ok: bool
    provider_id: str = ""
    error: str = ""
    code: int = 0


def is_configured():
    return bool(settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN
                and (settings.TWILIO_MESSAGING_SERVICE_SID or settings.TWILIO_FROM_NUMBER))


def _post_to_twilio(to, body):
    """One API call to Twilio. Kept separate so tests can replace it."""
    sid, token = settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN
    fields = {"To": to, "Body": body}
    if settings.TWILIO_MESSAGING_SERVICE_SID:
        fields["MessagingServiceSid"] = settings.TWILIO_MESSAGING_SERVICE_SID
    else:
        fields["From"] = settings.TWILIO_FROM_NUMBER
    request = urllib.request.Request(
        f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
        data=urllib.parse.urlencode(fields).encode(),
        headers={"Authorization": "Basic " + base64.b64encode(f"{sid}:{token}".encode()).decode()},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return Result(ok=True, provider_id=json.load(response).get("sid", ""))
    except urllib.error.HTTPError as exc:
        try:
            detail = json.load(exc)
        except ValueError:
            detail = {}
        return Result(ok=False, error=str(detail.get("message") or exc)[:255],
                      code=int(detail.get("code") or 0))
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return Result(ok=False, error=f"Could not reach Twilio: {exc}"[:255])


def send(profile, body, kind, dot=None, meeting_date=None):
    """Text one member, recording it. Returns the SmsLog, or None if nothing was attempted.

    Nothing is attempted when texting isn't configured, the member hasn't opted in or has no
    number, or (for reminders) this member was already texted about this meeting.
    """
    if not is_configured() or not profile.sms_opt_in or not profile.phone:
        return None
    try:
        with transaction.atomic():
            entry = SmsLog.objects.create(
                user=profile.user, phone=profile.phone, kind=kind, dot=dot,
                meeting_date=meeting_date, body=body)
    except IntegrityError:
        return None                                   # already reminded for this meeting
    result = _post_to_twilio(profile.phone, body)
    if not result.ok and result.code == 0 and kind == SmsLog.Kind.REMINDER:
        # Twilio couldn't be reached at all: forget this attempt so the next run tries again.
        log.warning("SMS to %s not sent (will retry): %s", profile.member_id, result.error)
        entry.delete()
        return None
    entry.status = SmsLog.Status.SENT if result.ok else SmsLog.Status.FAILED
    entry.provider_id, entry.error = result.provider_id, result.error
    entry.save(update_fields=["status", "provider_id", "error"])
    if result.code == TWILIO_OPTED_OUT:
        set_opt_in(profile, False)
    if not result.ok:
        log.warning("SMS to %s failed: %s", profile.member_id, result.error)
    return entry


def set_opt_in(profile, opted_in):
    from django.utils import timezone
    profile.sms_opt_in = opted_in
    profile.sms_opt_in_at = timezone.now() if opted_in else None
    profile.save(update_fields=["sms_opt_in", "sms_opt_in_at", "updated_at"])


def valid_twilio_signature(url, params, signature):
    """Check that an incoming webhook really came from Twilio (their documented HMAC-SHA1 scheme)."""
    token = settings.TWILIO_AUTH_TOKEN
    if not token or not signature:
        return False
    payload = url + "".join(f"{key}{params[key]}" for key in sorted(params))
    digest = hmac.new(token.encode(), payload.encode(), hashlib.sha1).digest()
    return hmac.compare_digest(base64.b64encode(digest).decode(), signature)
