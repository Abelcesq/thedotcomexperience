"""Send the member site's email (verification codes, password resets) through Resend."""
import json
import logging
import urllib.error
import urllib.request

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

log = logging.getLogger(__name__)


def _post(payload):
    """One API call to Resend. Kept separate so tests can replace it."""
    request = urllib.request.Request(
        "https://api.resend.com/emails", data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}",
                 "Content-Type": "application/json",
                 "User-Agent": "TheDotComExperience-Members/1.0"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.status


class ResendEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        sent = 0
        for message in email_messages or []:
            payload = {"from": message.from_email or settings.DEFAULT_FROM_EMAIL,
                       "to": list(message.to), "subject": message.subject, "text": message.body}
            if message.cc:
                payload["cc"] = list(message.cc)
            if message.bcc:
                payload["bcc"] = list(message.bcc)
            if message.reply_to:
                payload["reply_to"] = list(message.reply_to)
            for content, mimetype in getattr(message, "alternatives", []) or []:
                if mimetype == "text/html":
                    payload["html"] = content
            try:
                _post(payload)
                sent += 1
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                detail = exc.read().decode(errors="replace")[:300] if hasattr(exc, "read") else str(exc)
                log.error("Email to %s not sent: %s", message.to, detail)
                if not self.fail_silently:
                    raise
        return sent
