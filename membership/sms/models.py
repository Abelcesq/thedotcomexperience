from django.conf import settings
from django.db import models
from django.db.models import Q


class SmsLog(models.Model):
    """Every text the site sent (or tried to send). Also what stops a reminder going out twice."""

    class Kind(models.TextChoices):
        REMINDER = "reminder", "Dot reminder"
        CONFIRMATION = "confirmation", "Opt-in confirmation"
        TEST = "test", "Test message"

    class Status(models.TextChoices):
        SENDING = "sending", "Sending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                             blank=True, related_name="sms_logs")
    phone = models.CharField(max_length=20)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    dot = models.ForeignKey("dots.Dot", on_delete=models.SET_NULL, null=True, blank=True,
                            related_name="sms_logs")
    meeting_date = models.DateField(null=True, blank=True)   # which meeting a reminder was for
    body = models.CharField(max_length=480)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.SENDING)
    provider_id = models.CharField(max_length=64, blank=True)
    error = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # One reminder per member, per Dot, per meeting — however often the job runs.
            models.UniqueConstraint(
                fields=["user", "dot", "meeting_date"], condition=Q(kind="reminder"),
                name="one_reminder_per_member_per_meeting"),
        ]

    def __str__(self):
        return f"{self.get_kind_display()} to {self.phone} ({self.get_status_display()})"
