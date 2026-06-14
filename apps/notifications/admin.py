from django.contrib import admin

from apps.notifications.models import Notification, NotificationSettings


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("type", "user", "title", "read_at", "created_at")
    list_filter = ("type",)
    search_fields = ("user__phone_e164", "title")


@admin.register(NotificationSettings)
class NotificationSettingsAdmin(admin.ModelAdmin):
    list_display = ("user", "push_enabled", "email_enabled", "updated_at")
