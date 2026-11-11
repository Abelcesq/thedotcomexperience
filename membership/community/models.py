"""Member-to-member features: connections, private messages, blocks and reports."""
from django.conf import settings
from django.db import models
from django.db.models import Q

User = settings.AUTH_USER_MODEL


class Connection(models.Model):
    """A connection between two members. One row per pair; a declined request is deleted."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Connected"

    requester = models.ForeignKey(User, on_delete=models.CASCADE, related_name="connections_sent")
    addressee = models.ForeignKey(User, on_delete=models.CASCADE, related_name="connections_received")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["requester", "addressee"], name="unique_connection_pair"),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.requester} → {self.addressee} ({self.get_status_display()})"

    @classmethod
    def between(cls, a, b):
        """The connection row for this pair in either direction, or None."""
        return cls.objects.filter(
            Q(requester=a, addressee=b) | Q(requester=b, addressee=a)
        ).first()

    @classmethod
    def accepted_for(cls, user):
        return cls.objects.filter(
            Q(requester=user) | Q(addressee=user), status=cls.Status.ACCEPTED
        )

    def other(self, user):
        return self.addressee if self.requester_id == user.id else self.requester


class Message(models.Model):
    """A private message between two members."""

    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="messages_sent")
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="messages_received")
    body = models.TextField(max_length=settings.COMMUNITY_MESSAGE_MAX_LENGTH)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["recipient", "read_at"]),
            models.Index(fields=["sender", "recipient", "created_at"]),
        ]

    def __str__(self):
        return f"{self.sender} → {self.recipient} at {self.created_at:%Y-%m-%d %H:%M}"

    @classmethod
    def thread(cls, a, b):
        return cls.objects.filter(
            Q(sender=a, recipient=b) | Q(sender=b, recipient=a)
        ).select_related("sender")


class Block(models.Model):
    """One member blocking another: no profile view, connection, or messages either way."""

    blocker = models.ForeignKey(User, on_delete=models.CASCADE, related_name="blocks_made")
    blocked = models.ForeignKey(User, on_delete=models.CASCADE, related_name="blocks_received")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["blocker", "blocked"], name="unique_block_pair"),
        ]

    def __str__(self):
        return f"{self.blocker} blocked {self.blocked}"

    @classmethod
    def exists_between(cls, a, b):
        return cls.objects.filter(
            Q(blocker=a, blocked=b) | Q(blocker=b, blocked=a)
        ).exists()


class Report(models.Model):
    """A member reporting another member (or a specific message) for staff review."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        REVIEWED = "reviewed", "Reviewed"
        ACTIONED = "actioned", "Action taken"

    reporter = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="reports_made")
    reported = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reports_received")
    reason = models.TextField(max_length=1000)
    # A copy of the recent conversation at the moment of the report, so staff review
    # only what was reported rather than browsing private messages.
    conversation_snapshot = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    staff_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Report on {self.reported} ({self.get_status_display()})"
