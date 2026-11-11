import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


def generate_member_id():
    """A short, unique, non-sequential Member ID, e.g. DX-482913.

    Random rather than sequential so an ID never reveals how many members exist.
    """
    return "DX-" + "".join(secrets.choice("0123456789") for _ in range(6))


class Profile(models.Model):
    """One-to-one extension of the Django User: membership, Stripe, and member details."""

    class Role(models.TextChoices):
        """The membership tier. Everyone starts as a Member; the Company grants the rest."""
        MEMBER = "member", "Member"
        AMBASSADOR = "ambassador", "Ambassador"
        LOCAL_LEADER = "local_leader", "Local Leader"
        REGIONAL = "regional", "Regional"
        ADMIN = "admin", "Admin"

    # Who each tier reports to (the tier directly above it). None = top of the ladder.
    UPLINE_ROLE = {
        "member": "ambassador",
        "ambassador": "local_leader",
        "local_leader": "regional",
        "regional": None,
        "admin": None,
    }

    class MembershipStatus(models.TextChoices):
        INCOMPLETE = "incomplete", "Incomplete"      # signed up, not yet paid
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Past due"
        CANCELED = "canceled", "Canceled"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )

    # Unique, permanent Member ID (assigned automatically; used to link the organization).
    member_id = models.CharField(max_length=12, unique=True, editable=False, db_index=True)

    # Member details (the CEO's requested fields)
    display_name = models.CharField(max_length=120, blank=True)
    city = models.CharField(max_length=120, blank=True)       # used to match them to a local Dot
    phone = models.CharField(max_length=20, blank=True)       # E.164, e.g. +13105551234
    sms_opt_in = models.BooleanField(default=False)           # explicit consent to text

    # Code of Conduct consent (required at signup)
    coc_agreed = models.BooleanField(default=False)
    coc_agreed_at = models.DateTimeField(null=True, blank=True)

    # Community profile (what other members can see)
    bio = models.CharField(max_length=300, blank=True)
    directory_visible = models.BooleanField(
        default=True,
        help_text="Show this member in the member directory and let other members view their profile.",
    )

    # Tier + place in the organization
    role = models.CharField("tier", max_length=20, choices=Role.choices, default=Role.MEMBER)
    role_since = models.DateTimeField(null=True, blank=True)
    reports_to = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="downline",
        verbose_name="reports to (upline)",
        help_text="A Member reports to an Ambassador, an Ambassador to a Local Leader, "
                  "a Local Leader to a Regional.",
    )

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
        return f"{self.member_id} · {self.name} ({self.get_role_display()})"

    # --- Identity -----------------------------------------------------------
    def save(self, *args, **kwargs):
        if not self.member_id:
            candidate = generate_member_id()
            while Profile.objects.filter(member_id=candidate).exists():
                candidate = generate_member_id()
            self.member_id = candidate
        if self.role_since is None:
            self.role_since = timezone.now()
        super().save(*args, **kwargs)

    @property
    def name(self):
        """The name other members see. Never falls back to the email address."""
        return self.display_name or self.user.get_full_name() or self.user.first_name or "Member"

    @property
    def initials(self):
        parts = [p for p in self.name.split() if p]
        return ("".join(p[0] for p in parts[:2]) or "M").upper()

    # --- Membership / tier --------------------------------------------------
    @property
    def is_active_member(self):
        return self.membership_status == self.MembershipStatus.ACTIVE

    @property
    def is_charter_holder(self):
        return self.role in (self.Role.AMBASSADOR, self.Role.LOCAL_LEADER, self.Role.REGIONAL)

    @property
    def is_ambassador(self):
        return self.role in (self.Role.AMBASSADOR, self.Role.ADMIN)

    @property
    def can_use_community(self):
        """Directory, connections and messages are for active members and Charter holders."""
        return self.is_active_member or self.is_charter_holder or self.user.is_staff

    @property
    def expected_upline_role(self):
        return self.UPLINE_ROLE.get(self.role)

    @property
    def expected_upline_label(self):
        role = self.expected_upline_role
        return self.Role(role).label if role else ""

    def clean(self):
        super().clean()
        if self.reports_to_id:
            if self.reports_to_id == self.pk:
                raise ValidationError({"reports_to": "A member cannot report to themselves."})
            wanted = self.expected_upline_role
            if wanted is None:
                raise ValidationError(
                    {"reports_to": f"A {self.get_role_display()} is at the top of the ladder and has no upline."})
            if self.reports_to.role != wanted:
                raise ValidationError({"reports_to": (
                    f"A {self.get_role_display()} reports to a {self.Role(wanted).label}, "
                    f"but {self.reports_to.name} is a {self.reports_to.get_role_display()}.")})

    def change_role(self, new_role, by=None, note=""):
        """Move this person to a new tier, keeping the organization consistent.

        Returns the number of people who were un-assigned because they can no longer
        report to this person (or because this person no longer fits under their upline).
        """
        old_role = self.role
        if new_role == old_role:
            return 0
        self.role = new_role
        self.role_since = timezone.now()
        # Their own upline is only valid if it is the tier directly above the new tier.
        wanted = self.UPLINE_ROLE.get(new_role)
        if self.reports_to_id and (wanted is None or self.reports_to.role != wanted):
            self.reports_to = None
        self.save()
        # Anyone below them who no longer fits is un-assigned so the admin can re-place them.
        orphaned = 0
        for person in self.downline.all():
            if self.UPLINE_ROLE.get(person.role) != new_role:
                person.reports_to = None
                person.save(update_fields=["reports_to", "updated_at"])
                orphaned += 1
        TierChange.objects.create(
            profile=self, from_role=old_role, to_role=new_role, changed_by=by, note=note)
        return orphaned

    # --- Organization counts (what the admin report and "My team" show) -------
    def direct_reports(self, role=None):
        qs = self.downline.select_related("user")
        return qs.filter(role=role) if role else qs

    def team_members(self):
        """Every Member (non-Charter-holder) in this person's organization."""
        R = self.Role
        if self.role == R.AMBASSADOR:
            return Profile.objects.filter(reports_to=self, role=R.MEMBER)
        if self.role == R.LOCAL_LEADER:
            return Profile.objects.filter(reports_to__reports_to=self, role=R.MEMBER,
                                          reports_to__role=R.AMBASSADOR)
        if self.role == R.REGIONAL:
            return Profile.objects.filter(reports_to__reports_to__reports_to=self, role=R.MEMBER,
                                          reports_to__role=R.AMBASSADOR,
                                          reports_to__reports_to__role=R.LOCAL_LEADER)
        return Profile.objects.none()

    def team_ambassadors(self):
        R = self.Role
        if self.role == R.LOCAL_LEADER:
            return Profile.objects.filter(reports_to=self, role=R.AMBASSADOR)
        if self.role == R.REGIONAL:
            return Profile.objects.filter(reports_to__reports_to=self, role=R.AMBASSADOR,
                                          reports_to__role=R.LOCAL_LEADER)
        return Profile.objects.none()

    def team_local_leaders(self):
        if self.role == self.Role.REGIONAL:
            return Profile.objects.filter(reports_to=self, role=self.Role.LOCAL_LEADER)
        return Profile.objects.none()

    def team_stats(self):
        """Counts for this person's organization. "active" = genuine, paying, non-Charter members."""
        active = self.MembershipStatus.ACTIVE
        members = self.team_members()
        caps = settings.TIER_CAPS
        cap_key = {"ambassador": "members_per_ambassador",
                   "local_leader": "ambassadors_per_local_leader",
                   "regional": "local_leaders_per_regional"}.get(self.role)
        direct = self.downline.count()
        cap = caps.get(cap_key) if cap_key else None
        return {
            "members": members.count(),
            "active_members": members.filter(membership_status=active).count(),
            "ambassadors": self.team_ambassadors().count(),
            "local_leaders": self.team_local_leaders().count(),
            "direct": direct,
            "cap": cap,
            "over_cap": bool(cap and direct > cap),
            "at_cap": bool(cap and direct >= cap),
        }

    def record_coc_agreement(self):
        self.coc_agreed = True
        self.coc_agreed_at = timezone.now()


class TierChange(models.Model):
    """An audit trail of every tier change (who moved whom, and when)."""

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="tier_changes")
    from_role = models.CharField(max_length=20, choices=Profile.Role.choices)
    to_role = models.CharField(max_length=20, choices=Profile.Role.choices)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="tier_changes_made",
    )
    note = models.CharField(max_length=255, blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at"]

    def __str__(self):
        return (f"{self.profile.member_id}: {self.get_from_role_display()} → "
                f"{self.get_to_role_display()} on {self.changed_at:%Y-%m-%d}")
