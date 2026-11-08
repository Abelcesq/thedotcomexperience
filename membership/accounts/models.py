from django.conf import settings
from django.db import models
from django.utils import timezone


class Profile(models.Model):
    """One-to-one extension of the Django User: membership, Stripe, and member details."""

    class Role(models.TextChoices):
        MEMBER = "member", "Member"
        AMBASSADOR = "ambassador", "Ambassador"
        ADMIN = "admin", "Admin"

    class MembershipStatus(models.TextChoices):
        INCOMPLETE = "incomplete", "Incomplete"      # signed up, not yet paid
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Past due"
        CANCELED = "canceled", "Canceled"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )

    # Member details (the CEO's requested fields)
    display_name = models.CharField(max_length=120, blank=True)
    city = models.CharField(max_length=120, blank=True)       # used to match them to a local Dot
    phone = models.CharField(max_length=20, blank=True)       # E.164, e.g. +13105551234
    sms_opt_in = models.BooleanField(default=False)           # explicit consent to text

    # Code of Conduct consent (required at signup)
    coc_agreed = models.BooleanField(default=False)
    coc_agreed_at = models.DateTimeField(null=True, blank=True)

    # Role / access
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)

    # Stripe / membership (webhook is the source of truth)
    stripe_customer_id = models.CharField(max_length=64, blank=True)
    stripe_subscription_id = models.CharField(max_length=64, blank=True)
    membership_status = models.CharField(
        max_length=20, choices=MembershipStatus.choices, default=MembershipStatus.INCOMPLETE
    )
    current_period_end = models.DateTimeField(null=True, blank=True)
    price_id = models.CharField(max_length=64, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email or self.user.username} ({self.get_membership_status_display()})"

    @property
    def is_active_member(self):
        return self.membership_status == self.MembershipStatus.ACTIVE

    @property
    def is_ambassador(self):
        return self.role in (self.Role.AMBASSADOR, self.Role.ADMIN)

    def record_coc_agreement(self):
        self.coc_agreed = True
        self.coc_agreed_at = timezone.now()
