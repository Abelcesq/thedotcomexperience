from django.db import models


class WebhookEvent(models.Model):
    """A log of Stripe webhook events we've processed — for dedup and auditing.

    Stripe can deliver the same event more than once; recording the event id lets
    us skip duplicates, and keeps a trail of what came in and when.
    """
    stripe_event_id = models.CharField(max_length=255, unique=True)
    type = models.CharField(max_length=100)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at"]

    def __str__(self):
        return f"{self.type} · {self.stripe_event_id}"
