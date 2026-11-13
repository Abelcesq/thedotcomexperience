from zoneinfo import available_timezones

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.utils import timezone as djtz

from .geocode import geocode_city
from .models import Dot, DotApplication, DotMembership, Waitlist
from .schedule import reminder_time

COMMON_ZONES = ["America/Los_Angeles", "America/Denver", "America/Phoenix", "America/Chicago",
                "America/New_York", "America/Anchorage", "Pacific/Honolulu"]


def _timezone_choices():
    rest = sorted(z for z in available_timezones() if "/" in z and not z.startswith(("Etc/", "posix/", "right/"))
                  and z not in COMMON_ZONES)
    return [(z, z.replace("_", " ")) for z in COMMON_ZONES + rest]


class DotMembershipInline(admin.TabularInline):
    model = DotMembership
    extra = 0
    autocomplete_fields = ("user",)


@admin.register(Dot)
class DotAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "status", "has_coords", "meeting_night", "meeting_time",
                    "next_reminder", "ambassador", "seats_taken", "capacity")
    list_filter = ("status", "city")
    search_fields = ("name", "city", "region", "location")
    autocomplete_fields = ("ambassador",)
    inlines = [DotMembershipInline]
    actions = ["regeocode_from_city"]
    fieldsets = (
        (None, {"fields": ("name", "city", "region", "location", "status", "description")}),
        ("Map coordinates", {
            "fields": ("lat", "lng"),
            "description": "Leave blank and we'll look them up from the city when you save. "
                           "Fill them in to set an exact spot.",
        }),
        ("Meeting & people", {
            "fields": ("meeting_night", "meeting_time", "timezone", "ambassador", "capacity"),
            "description": "Enter the day (for example Tuesday) and start time (for example 7:00 PM). "
                           "Members with a seat here who opted in to texts get a reminder before each meeting.",
        }),
    )

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "timezone":
            return forms.ChoiceField(choices=_timezone_choices(), initial="America/Los_Angeles",
                                     label="Time zone", help_text=db_field.help_text)
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    @admin.display(description="Next reminder text")
    def next_reminder(self, obj):
        if obj.status == Dot.Status.PAUSED:
            return "Paused"
        start = obj.next_meeting()
        if not start:
            return "No meeting day/time set"
        send_at = reminder_time(start, settings.SMS_REMINDER_HOURS_BEFORE,
                                settings.SMS_QUIET_START_HOUR, settings.SMS_QUIET_END_HOUR)
        if send_at <= djtz.now().astimezone(start.tzinfo):
            return "Sending now for " + start.strftime("%a %b %-d")
        return send_at.strftime("%a %b %-d, %-I:%M %p %Z")

    @admin.display(boolean=True, description="On map")
    def has_coords(self, obj):
        return obj.lat is not None and obj.lng is not None

    def save_model(self, request, obj, form, change):
        """Auto-fill coordinates from the city name when they're missing."""
        if (obj.lat is None or obj.lng is None) and obj.city:
            coords = geocode_city(obj.city, obj.region)
            if coords:
                obj.lat, obj.lng = coords
                self.message_user(
                    request, f"Located {obj.city} at {obj.lat}, {obj.lng}.", level=messages.SUCCESS)
            else:
                self.message_user(
                    request,
                    f"Couldn't look up coordinates for “{obj.city}”. It won't appear on the map "
                    "until you add latitude/longitude manually.", level=messages.WARNING)
        super().save_model(request, obj, form, change)

    @admin.action(description="Re-look up coordinates from the city name")
    def regeocode_from_city(self, request, queryset):
        found, missed = 0, 0
        for dot in queryset:
            coords = geocode_city(dot.city, dot.region)
            if coords:
                dot.lat, dot.lng = coords
                dot.save(update_fields=["lat", "lng"])
                found += 1
            else:
                missed += 1
        if found:
            self.message_user(request, f"Updated coordinates for {found} Dot(s).", messages.SUCCESS)
        if missed:
            self.message_user(request, f"Couldn't locate {missed} Dot(s) by city name.", messages.WARNING)


@admin.register(Waitlist)
class WaitlistAdmin(admin.ModelAdmin):
    list_display = ("email", "first_name", "city", "intent", "created_at")
    list_filter = ("intent", "city")
    search_fields = ("email", "first_name", "city")


@admin.register(DotApplication)
class DotApplicationAdmin(admin.ModelAdmin):
    list_display = ("full_name", "city", "email", "status", "created_at")
    list_filter = ("status", "city")
    search_fields = ("full_name", "email", "city")
    readonly_fields = ("created_at", "updated_at")
    actions = ["mark_reviewing", "mark_approved", "mark_declined"]

    @admin.action(description="Mark: in review")
    def mark_reviewing(self, request, queryset):
        queryset.update(status=DotApplication.Status.REVIEWING)

    @admin.action(description="Mark: approved")
    def mark_approved(self, request, queryset):
        queryset.update(status=DotApplication.Status.APPROVED)

    @admin.action(description="Mark: declined")
    def mark_declined(self, request, queryset):
        queryset.update(status=DotApplication.Status.DECLINED)
