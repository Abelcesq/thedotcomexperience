from django.contrib import admin

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user", "role", "membership_status", "city",
        "sms_opt_in", "coc_agreed", "current_period_end",
    )
    list_filter = ("role", "membership_status", "sms_opt_in", "coc_agreed")
    search_fields = ("user__email", "user__username", "display_name", "city",
                     "stripe_customer_id", "stripe_subscription_id")
    readonly_fields = ("stripe_customer_id", "stripe_subscription_id",
                       "current_period_end", "price_id", "coc_agreed_at",
                       "created_at", "updated_at")
    actions = ["make_ambassador", "make_member"]

    @admin.action(description="Promote selected to Ambassador")
    def make_ambassador(self, request, queryset):
        updated = queryset.update(role=Profile.Role.AMBASSADOR)
        self.message_user(request, f"{updated} member(s) promoted to Ambassador.")

    @admin.action(description="Set selected back to Member")
    def make_member(self, request, queryset):
        updated = queryset.update(role=Profile.Role.MEMBER)
        self.message_user(request, f"{updated} set to Member.")
