from django.contrib import admin

from .models import Dot, DotApplication, DotMembership, Waitlist


class DotMembershipInline(admin.TabularInline):
    model = DotMembership
    extra = 0
    autocomplete_fields = ("user",)


@admin.register(Dot)
class DotAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "status", "meeting_night", "meeting_time",
                    "ambassador", "seats_taken", "capacity")
    list_filter = ("status", "city")
    search_fields = ("name", "city", "region", "location")
    autocomplete_fields = ("ambassador",)
    inlines = [DotMembershipInline]


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
