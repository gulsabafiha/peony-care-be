from __future__ import annotations

from apps.accounts.models import User
from apps.common.choices import UserRole
from apps.common.exceptions import PeonyAPIException
from apps.notifications.models import NotificationSettings

SETTINGS_FIELDS = (
    "push_enabled",
    "email_enabled",
    "alert_new_claim",
    "alert_sponsored",
    "alert_all_claimed",
    "alert_window_expiring",
    "alert_no_show",
    "alert_donation_claimed",
    "alert_receipts",
)


def _ensure_restaurant(user: User) -> None:
    if user.role != UserRole.RESTAURANT:
        raise PeonyAPIException(
            code="FORBIDDEN",
            message="Notification settings are only available for restaurant accounts.",
            http_status=403,
        )


def get_or_create_settings(user: User) -> NotificationSettings:
    settings_obj, _ = NotificationSettings.objects.get_or_create(user=user)
    return settings_obj


def serialize_notification_settings(settings_obj: NotificationSettings) -> dict:
    return {field: getattr(settings_obj, field) for field in SETTINGS_FIELDS} | {
        "updated_at": settings_obj.updated_at,
    }


def get_restaurant_notification_settings(user: User) -> dict:
    _ensure_restaurant(user)
    return serialize_notification_settings(get_or_create_settings(user))


def update_restaurant_notification_settings(user: User, data: dict) -> dict:
    _ensure_restaurant(user)
    settings_obj = get_or_create_settings(user)
    update_fields: list[str] = []
    for field in SETTINGS_FIELDS:
        if field in data:
            setattr(settings_obj, field, data[field])
            update_fields.append(field)
    if update_fields:
        settings_obj.save(update_fields=update_fields + ["updated_at"])
    return serialize_notification_settings(settings_obj)
