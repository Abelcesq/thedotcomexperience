from django.conf import settings
from django.db import models


class Dot(models.Model):
    """A local circle (~8–12 people) that meets weekly in person."""

    class Status(models.TextChoices):
        FORMING = "forming", "Forming"
        ACTIVE = "active", "Active"
        FULL = "full", "Full"
        PAUSED = "paused", "Paused"

    name = models.CharField(max_length=120)
    city = models.CharField(max_length=120, db_index=True)
    region = models.CharField(max_length=120, blank=True)      # state / province
    location = models.CharField(max_length=255, blank=True)    # address or venue
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    meeting_night = models.CharField(max_length=20, blank=True)  # e.g. "Tuesday"
    meeting_time = models.CharField(max_length=20, blank=True)   # e.g. "7:00 PM"
    ambassador = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="dots_led",
    )
    capacity = models.PositiveSmallIntegerField(default=12)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.FORMING)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["city", "name"]

    def __str__(self):
        return f"{self.name} — {self.city}"

    @property
    def seats_taken(self):
        return self.memberships.count()

    @property
    def has_space(self):
        return self.status != self.Status.FULL and self.seats_taken < self.capacity


class DotMembership(models.Model):
    """A member's seat in a Dot."""
    dot = models.ForeignKey(Dot, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="dot_memberships")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("dot", "user")

    def __str__(self):
        return f"{self.user} in {self.dot}"


class Waitlist(models.Model):
    """Interest capture when there's no Dot yet (mirrors the Node /api/subscribe funnel)."""

    class Intent(models.TextChoices):
        JOIN = "join", "Join a Dot"
        REQUEST = "request_location", "Request a new Dot location"

    first_name = models.CharField(max_length=60, blank=True)
    email = models.EmailField()
    city = models.CharField(max_length=120, blank=True, db_index=True)
    intent = models.CharField(max_length=20, choices=Intent.choices, default=Intent.JOIN)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.email} ({self.city or 'no city'} / {self.get_intent_display()})"


class DotApplication(models.Model):
    """An application to charter and lead a new Dot (vetted, to keep every Dot consistent)."""

    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        REVIEWING = "reviewing", "In review"
        TRAINING = "training", "In training"
        APPROVED = "approved", "Approved"
        DECLINED = "declined", "Declined"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="dot_applications",
    )
    full_name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    city = models.CharField(max_length=120)
    why = models.TextField(blank=True, help_text="Why they want to lead a Dot in their city.")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUBMITTED)
    review_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} — {self.city} ({self.get_status_display()})"
