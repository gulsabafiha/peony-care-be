from __future__ import annotations

from django.utils import timezone

from apps.accounts.models import ReceiverProfile, RestaurantProfile, User
from apps.common.exceptions import PeonyAPIException
from apps.donations.models import FoodItem
from apps.notifications.models import Notification

DEFAULT_NOTIFICATION_LIMIT = 50
MAX_NOTIFICATION_LIMIT = 100


def get_unread_count(user: User) -> dict:
    return {
        "unread_count": Notification.objects.filter(user=user, read_at__isnull=True).count(),
    }


def _serialize_notification(notification: Notification) -> dict:
    return {
        "id": str(notification.id),
        "type": notification.type,
        "title": notification.title,
        "body": notification.body,
        "payload": notification.payload or {},
        "is_read": notification.read_at is not None,
        "read_at": notification.read_at.isoformat() if notification.read_at else None,
        "created_at": notification.created_at.isoformat(),
    }


def list_notifications(
    user: User,
    *,
    unread_only: bool = False,
    limit: int = DEFAULT_NOTIFICATION_LIMIT,
) -> dict:
    limit = max(1, min(limit, MAX_NOTIFICATION_LIMIT))
    queryset = Notification.objects.filter(user=user)
    if unread_only:
        queryset = queryset.filter(read_at__isnull=True)

    notifications = list(queryset.order_by("-created_at")[:limit])
    unread_count = Notification.objects.filter(user=user, read_at__isnull=True).count()
    return {
        "items": [_serialize_notification(n) for n in notifications],
        "unread_count": unread_count,
    }


def mark_notification_read(user: User, notification_id: str) -> dict:
    try:
        notification = Notification.objects.get(id=notification_id, user=user)
    except Notification.DoesNotExist as exc:
        raise PeonyAPIException(
            code="NOTIFICATION_NOT_FOUND",
            message="Notification not found.",
            http_status=404,
        ) from exc

    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at"])

    return _serialize_notification(notification)


def mark_all_notifications_read(user: User) -> dict:
    updated = Notification.objects.filter(user=user, read_at__isnull=True).update(
        read_at=timezone.now()
    )
    return {
        "marked_read": updated,
        "unread_count": 0,
    }


def notify_nearby_receivers_of_new_food(
    food: FoodItem,
    restaurant: RestaurantProfile,
    nearby_receivers: list[tuple[ReceiverProfile, float]],
) -> int:
    """Create in-app NEW_FOOD_NEARBY notifications for nearby receivers."""
    if not nearby_receivers:
        return 0

    notifications = [
        Notification(
            user=receiver.user,
            type="NEW_FOOD_NEARBY",
            title="New food near you",
            body=f"{restaurant.name} just posted {food.name} nearby.",
            payload={
                "food_id": str(food.id),
                "restaurant_id": str(restaurant.id),
                "distance_km": round(distance_m / 1000, 1),
            },
        )
        for receiver, distance_m in nearby_receivers
    ]
    Notification.objects.bulk_create(notifications)
    return len(notifications)
