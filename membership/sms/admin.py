from django.contrib import admin

from .models import SmsLog


@admin.register(SmsLog)
class SmsLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "kind", "phone", "user", "dot", "meeting_date", "status", "error")
    list_filter = ("kind", "status")
    search_fields = ("phone", "user__email", "body", "provider_id")
    readonly_fields = [f.name for f in SmsLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
