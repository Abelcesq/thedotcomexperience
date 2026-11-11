from django.contrib import admin

from .models import Block, Connection, Report

# Private messages are deliberately NOT registered here: staff review a conversation
# only when a member reports it (the report carries a snapshot of what was reported).


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("created_at", "reported", "reporter", "status")
    list_filter = ("status",)
    search_fields = ("reported__email", "reporter__email", "reason")
    readonly_fields = ("reporter", "reported", "reason", "conversation_snapshot", "created_at")
    fields = ("status", "staff_notes", "reported", "reporter", "reason",
              "conversation_snapshot", "created_at")

    def has_add_permission(self, request):
        return False


@admin.register(Connection)
class ConnectionAdmin(admin.ModelAdmin):
    list_display = ("requester", "addressee", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("requester__email", "addressee__email")
    readonly_fields = ("requester", "addressee", "created_at", "responded_at")

    def has_add_permission(self, request):
        return False


@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ("blocker", "blocked", "created_at")
    search_fields = ("blocker__email", "blocked__email")
    readonly_fields = ("blocker", "blocked", "created_at")

    def has_add_permission(self, request):
        return False
