from django.contrib import admin

from apps.notifications.models import Notification, NotificationSettings


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("type", "user", "title", "read_at", "created_at")
    list_filter = ("type", "read_at")
    search_fields = ("user__phone_e164", "title", "body")
    readonly_fields = ("id", "created_at")
    autocomplete_fields = ("user",)
    ordering = ("-created_at",)


@admin.register(NotificationSettings)
class NotificationSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "push_enabled",
        "email_enabled",
        "alert_new_claim",
        "alert_sponsored",
        "updated_at",
    )
    list_filter = ("push_enabled", "email_enabled")
    search_fields = ("user__phone_e164",)
    readonly_fields = ("id", "updated_at")
    autocomplete_fields = ("user",)
