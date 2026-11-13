from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.html import format_html

from .models import Profile, TierChange

R = Profile.Role


class TierChangeInline(admin.TabularInline):
    model = TierChange
    fk_name = "profile"
    extra = 0
    can_delete = False
    fields = ("changed_at", "from_role", "to_role", "changed_by", "note")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


class AssignUplineForm(forms.Form):
    upline_member_id = forms.CharField(
        label="Upline's Member ID", max_length=12,
        help_text="The Member ID of the Ambassador, Local Leader, or Regional they will report to "
                  "(for example DX-482913).",
    )

    def clean_upline_member_id(self):
        value = self.cleaned_data["upline_member_id"].strip().upper()
        try:
            return Profile.objects.select_related("user").get(member_id=value)
        except Profile.DoesNotExist:
            raise forms.ValidationError("No member has that Member ID.")


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    change_list_template = "admin/accounts/profile_changelist.html"
    list_display = (
        "member_id", "member_name", "email", "role", "upline", "organization",
        "membership_status", "city", "current_period_end",
    )
    list_display_links = ("member_id", "member_name")
    list_filter = ("role", "membership_status", "directory_visible", "sms_opt_in", "coc_agreed")
    search_fields = ("member_id", "user__email", "user__username", "user__first_name",
                     "user__last_name", "display_name", "city",
                     "stripe_customer_id", "stripe_subscription_id")
    autocomplete_fields = ("reports_to",)
    list_select_related = ("user", "reports_to", "reports_to__user")
    readonly_fields = ("member_id", "role_since", "sms_opt_in_at", "stripe_customer_id", "stripe_subscription_id",
                       "current_period_end", "price_id", "coc_agreed_at",
                       "created_at", "updated_at")
    fieldsets = (
        ("Member", {"fields": ("user", "member_id", "display_name", "city", "bio", "directory_visible")}),
        ("Tier & organization", {
            "fields": ("role", "role_since", "reports_to"),
            "description": "Everyone starts as a Member. A Member reports to an Ambassador, an "
                           "Ambassador to a Local Leader, a Local Leader to a Regional.",
        }),
        ("Contact", {"fields": ("phone", "sms_opt_in", "sms_opt_in_at")}),
        ("Code of Conduct", {"fields": ("coc_agreed", "coc_agreed_at")}),
        ("Membership (Stripe is the source of truth)", {
            "fields": ("membership_status", "current_period_end", "stripe_customer_id",
                       "stripe_subscription_id", "price_id"),
        }),
        ("Record", {"fields": ("created_at", "updated_at")}),
    )
    inlines = [TierChangeInline]
    actions = ["make_ambassador", "make_local_leader", "make_regional", "make_member",
               "assign_upline", "clear_upline", "send_test_text"]

    # --- columns ---------------------------------------------------------------
    @admin.display(description="Name", ordering="display_name")
    def member_name(self, obj):
        return obj.name

    @admin.display(description="Email", ordering="user__email")
    def email(self, obj):
        return obj.user.email

    @admin.display(description="Reports to")
    def upline(self, obj):
        if not obj.reports_to_id:
            return "—"
        return f"{obj.reports_to.name} ({obj.reports_to.member_id})"

    @admin.display(description="Organization")
    def organization(self, obj):
        if not obj.is_charter_holder:
            return "—"
        s = obj.team_stats()
        if obj.role == R.AMBASSADOR:
            text = f"{s['members']} members ({s['active_members']} active) · cap {s['cap']}"
        elif obj.role == R.LOCAL_LEADER:
            text = (f"{s['ambassadors']}/{s['cap']} ambassadors · "
                    f"{s['members']} members ({s['active_members']} active)")
        else:
            text = (f"{s['local_leaders']}/{s['cap']} local leaders · {s['ambassadors']} ambassadors · "
                    f"{s['members']} members ({s['active_members']} active)")
        if s["over_cap"]:
            return format_html('<b style="color:#c0392b">{} — OVER CAP</b>', text)
        return text

    # --- saving a single profile --------------------------------------------------
    def save_model(self, request, obj, form, change):
        if change and "role" in form.changed_data:
            new_role = obj.role
            obj.role = form.initial.get("role", new_role)   # change_role() needs the old tier
            wanted_upline = obj.reports_to
            orphaned = obj.change_role(new_role, by=request.user, note="Changed in admin")
            if wanted_upline and wanted_upline.role == Profile.UPLINE_ROLE.get(new_role):
                obj.reports_to = wanted_upline
            super().save_model(request, obj, form, change)
            if orphaned:
                self.message_user(
                    request,
                    f"{orphaned} person(s) who reported to {obj.name} no longer fit under a "
                    f"{obj.get_role_display()} and were un-assigned. Re-assign them to a new upline.",
                    level=messages.WARNING)
        else:
            super().save_model(request, obj, form, change)
        self._warn_if_over_cap(request, obj.reports_to)

    def _warn_if_over_cap(self, request, upline):
        if not upline:
            return
        stats = upline.team_stats()
        if stats["over_cap"]:
            self.message_user(
                request,
                f"{upline.name} ({upline.member_id}) now has {stats['direct']} direct reports — "
                f"over the cap of {stats['cap']} for a {upline.get_role_display()}.",
                level=messages.WARNING)

    # --- bulk tier actions ------------------------------------------------------------
    def _set_tier(self, request, queryset, role):
        moved = orphaned = 0
        for profile in queryset:
            if profile.role != role:
                orphaned += profile.change_role(role, by=request.user, note="Bulk change in admin")
                moved += 1
        self.message_user(request, f"{moved} member(s) set to {R(role).label}.")
        if orphaned:
            self.message_user(
                request, f"{orphaned} person(s) were un-assigned from their upline and need re-assigning.",
                level=messages.WARNING)

    @admin.action(description="Set tier → Ambassador")
    def make_ambassador(self, request, queryset):
        self._set_tier(request, queryset, R.AMBASSADOR)

    @admin.action(description="Set tier → Local Leader")
    def make_local_leader(self, request, queryset):
        self._set_tier(request, queryset, R.LOCAL_LEADER)

    @admin.action(description="Set tier → Regional")
    def make_regional(self, request, queryset):
        self._set_tier(request, queryset, R.REGIONAL)

    @admin.action(description="Set tier → Member")
    def make_member(self, request, queryset):
        self._set_tier(request, queryset, R.MEMBER)

    @admin.action(description="Send a test text to selected (opted-in members only)")
    def send_test_text(self, request, queryset):
        from sms import reminders, service
        if not service.is_configured():
            self.message_user(
                request, "Texting isn't switched on yet: add the Twilio settings in Heroku first.",
                level=messages.ERROR)
            return
        sent, failed, skipped = 0, [], 0
        for profile in queryset:
            entry = reminders.send_test(profile)
            if entry is None:
                skipped += 1
            elif entry.status == "sent":
                sent += 1
            else:
                failed.append(f"{profile.name}: {entry.error}")
        if sent:
            self.message_user(request, f"Test text sent to {sent} member(s).")
        if skipped:
            self.message_user(
                request, f"{skipped} skipped: no phone number, or they haven't opted in to texts.",
                level=messages.WARNING)
        for line in failed:
            self.message_user(request, f"Failed — {line}", level=messages.ERROR)

    @admin.action(description="Remove selected from their upline")
    def clear_upline(self, request, queryset):
        updated = queryset.update(reports_to=None)
        self.message_user(request, f"{updated} member(s) un-assigned.")

    @admin.action(description="Assign selected to an upline (by Member ID)…")
    def assign_upline(self, request, queryset):
        form = AssignUplineForm(request.POST if "apply" in request.POST else None)
        if "apply" in request.POST and form.is_valid():
            upline = form.cleaned_data["upline_member_id"]
            assigned, skipped = 0, []
            for profile in queryset.select_related("user"):
                if profile.pk == upline.pk or Profile.UPLINE_ROLE.get(profile.role) != upline.role:
                    skipped.append(f"{profile.name} ({profile.get_role_display()})")
                    continue
                profile.reports_to = upline
                profile.save(update_fields=["reports_to", "updated_at"])
                assigned += 1
            self.message_user(
                request, f"{assigned} assigned to {upline.name} ({upline.get_role_display()}, {upline.member_id}).")
            if skipped:
                self.message_user(
                    request,
                    "Skipped — the wrong tier to report to a " + upline.get_role_display() + ": "
                    + ", ".join(skipped), level=messages.WARNING)
            self._warn_if_over_cap(request, upline)
            return None
        return render(request, "admin/accounts/assign_upline.html", {
            **self.admin_site.each_context(request),
            "title": "Assign to an upline",
            "form": form, "profiles": queryset, "opts": self.model._meta,
        })

    # --- organization report ------------------------------------------------------------
    def get_urls(self):
        custom = [path("organization/", self.admin_site.admin_view(self.organization_view),
                       name="accounts_profile_organization")]
        return custom + super().get_urls()

    def organization_view(self, request):
        active = Profile.MembershipStatus.ACTIVE
        everyone = Profile.objects.select_related("user", "reports_to")

        def node(profile):
            return {"profile": profile, "stats": profile.team_stats(), "children": []}

        regionals = []
        for regional in everyone.filter(role=R.REGIONAL).order_by("display_name"):
            r = node(regional)
            for ll in regional.direct_reports(R.LOCAL_LEADER):
                l = node(ll)
                l["children"] = [node(a) for a in ll.direct_reports(R.AMBASSADOR)]
                r["children"].append(l)
            regionals.append(r)

        unplaced_leaders = []
        for ll in everyone.filter(role=R.LOCAL_LEADER, reports_to__isnull=True).order_by("display_name"):
            l = node(ll)
            l["children"] = [node(a) for a in ll.direct_reports(R.AMBASSADOR)]
            unplaced_leaders.append(l)
        unplaced_ambassadors = [node(a) for a in everyone.filter(
            role=R.AMBASSADOR, reports_to__isnull=True).order_by("display_name")]

        members = everyone.filter(role=R.MEMBER)
        totals = {
            "members": members.count(),
            "active_members": members.filter(membership_status=active).count(),
            "unassigned_members": members.filter(reports_to__isnull=True).count(),
            "ambassadors": everyone.filter(role=R.AMBASSADOR).count(),
            "local_leaders": everyone.filter(role=R.LOCAL_LEADER).count(),
            "regionals": everyone.filter(role=R.REGIONAL).count(),
        }
        return render(request, "admin/accounts/organization.html", {
            **self.admin_site.each_context(request),
            "title": "Organization report",
            "opts": self.model._meta,
            "regionals": regionals,
            "unplaced_leaders": unplaced_leaders,
            "unplaced_ambassadors": unplaced_ambassadors,
            "totals": totals, "caps": settings.TIER_CAPS,
            "changelist_url": reverse("admin:accounts_profile_changelist"),
        })


@admin.register(TierChange)
class TierChangeAdmin(admin.ModelAdmin):
    list_display = ("changed_at", "profile", "from_role", "to_role", "changed_by", "note")
    list_filter = ("to_role", "from_role")
    search_fields = ("profile__member_id", "profile__display_name", "profile__user__email")
    readonly_fields = ("profile", "from_role", "to_role", "changed_by", "note", "changed_at")

    def has_add_permission(self, request):
        return False
