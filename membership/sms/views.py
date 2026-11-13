from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.models import Profile
from . import service

STOP_WORDS = {"STOP", "STOPALL", "UNSUBSCRIBE", "CANCEL", "END", "QUIT", "REVOKE", "OPTOUT"}
START_WORDS = {"START", "UNSTOP", "YES"}
EMPTY_REPLY = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'


@csrf_exempt
@require_POST
def inbound(request):
    """Twilio calls this when a member texts back. STOP switches their reminders off here too."""
    params = request.POST.dict()
    signature = request.headers.get("X-Twilio-Signature", "")
    urls = {settings.SITE_URL.rstrip("/") + request.get_full_path(), request.build_absolute_uri()}
    if not any(service.valid_twilio_signature(url, params, signature) for url in urls):
        return HttpResponseForbidden("Invalid signature")
    word = (params.get("Body") or "").strip().upper()
    sender = params.get("From") or ""
    if sender and word in STOP_WORDS | START_WORDS:
        for profile in Profile.objects.filter(phone=sender):
            service.set_opt_in(profile, word in START_WORDS)
    return HttpResponse(EMPTY_REPLY, content_type="text/xml")
