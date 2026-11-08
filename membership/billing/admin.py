from django.contrib import admin

from .models import WebhookEvent


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ("type", "stripe_event_id", "received_at")
    list_filter = ("type",)
    search_fields = ("stripe_event_id", "type")
    readonly_fields = ("stripe_event_id", "type", "received_at")

    def has_add_permission(self, request):
        return False  # written only by the webhook
