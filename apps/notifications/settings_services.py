from __future__ import annotations

from apps.accounts.models import User
from apps.common.choices import UserRole
from apps.common.exceptions import PeonyAPIException
from apps.notifications.models import NotificationSettings

RESTAURANT_SETTINGS_FIELDS = (
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

RECEIVER_SETTINGS_FIELDS = (
    "push_enabled",
    "alert_new_food_nearby",
    "alert_claim_confirmations",
    "alert_daily_limit_reset",
)

# Backwards-compatible alias used by restaurant export / older call sites.
SETTINGS_FIELDS = RESTAURANT_SETTINGS_FIELDS


def _ensure_restaurant(user: User) -> None:
    if user.role != UserRole.RESTAURANT:
        raise PeonyAPIException(
            code="FORBIDDEN",
            message="Notification settings are only available for restaurant accounts.",
            http_status=403,
        )


def _ensure_receiver(user: User) -> None:
    if user.role != UserRole.RECEIVER:
        raise PeonyAPIException(
            code="FORBIDDEN",
            message="Notification settings are only available for receiver accounts.",
            http_status=403,
        )


def get_or_create_settings(user: User) -> NotificationSettings:
    settings_obj, _ = NotificationSettings.objects.get_or_create(user=user)
    return settings_obj


def serialize_notification_settings(settings_obj: NotificationSettings) -> dict:
    return {field: getattr(settings_obj, field) for field in RESTAURANT_SETTINGS_FIELDS} | {
        "updated_at": settings_obj.updated_at,
    }


def serialize_receiver_notification_settings(settings_obj: NotificationSettings) -> dict:
    return {field: getattr(settings_obj, field) for field in RECEIVER_SETTINGS_FIELDS} | {
        "updated_at": settings_obj.updated_at,
    }


def _update_settings_fields(
    settings_obj: NotificationSettings,
    data: dict,
    fields: tuple[str, ...],
) -> NotificationSettings:
    update_fields: list[str] = []
    for field in fields:
        if field in data:
            setattr(settings_obj, field, data[field])
            update_fields.append(field)
    if update_fields:
        settings_obj.save(update_fields=update_fields + ["updated_at"])
    return settings_obj


def get_restaurant_notification_settings(user: User) -> dict:
    _ensure_restaurant(user)
    return serialize_notification_settings(get_or_create_settings(user))


def update_restaurant_notification_settings(user: User, data: dict) -> dict:
    _ensure_restaurant(user)
    settings_obj = _update_settings_fields(
        get_or_create_settings(user),
        data,
        RESTAURANT_SETTINGS_FIELDS,
    )
    return serialize_notification_settings(settings_obj)


def get_receiver_notification_settings(user: User) -> dict:
    _ensure_receiver(user)
    return serialize_receiver_notification_settings(get_or_create_settings(user))


def update_receiver_notification_settings(user: User, data: dict) -> dict:
    _ensure_receiver(user)
    settings_obj = _update_settings_fields(
        get_or_create_settings(user),
        data,
        RECEIVER_SETTINGS_FIELDS,
    )
    return serialize_receiver_notification_settings(settings_obj)


def receiver_allows_alert(user: User, alert_field: str) -> bool:
    """Return whether a receiver should receive a given alert type."""
    settings_obj = NotificationSettings.objects.filter(user=user).first()
    if settings_obj is None:
        return True
    if not settings_obj.push_enabled:
        return False
    return bool(getattr(settings_obj, alert_field, True))
