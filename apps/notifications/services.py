from __future__ import annotations

from collections import defaultdict
from datetime import date

from django.core.paginator import Paginator
from django.utils import timezone

from apps.accounts.models import ReceiverProfile, RestaurantProfile, User
from apps.common.exceptions import PeonyAPIException
from apps.common.timezone_utils import SGT, format_day_label, today_sgt
from apps.donations.models import FoodItem
from apps.notifications.models import Notification

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


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


def _notification_day(notification: Notification) -> date:
    return notification.created_at.astimezone(SGT).date()


def _group_notifications_by_date(
    notifications: list[Notification],
    *,
    today: date | None = None,
) -> list[dict]:
    today = today or today_sgt()
    buckets: dict[date, list[Notification]] = defaultdict(list)
    for notification in notifications:
        buckets[_notification_day(notification)].append(notification)

    groups = []
    for day in sorted(buckets.keys(), reverse=True):
        items = buckets[day]
        groups.append(
            {
                "key": day.isoformat(),
                "label": format_day_label(day, today=today),
                "date": day.isoformat(),
                "count": len(items),
                "items": [_serialize_notification(n) for n in items],
            }
        )
    return groups


def list_notifications(
    user: User,
    *,
    unread_only: bool = False,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> dict:
    page = max(1, page)
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))

    queryset = Notification.objects.filter(user=user).order_by("-created_at")
    if unread_only:
        queryset = queryset.filter(read_at__isnull=True)

    paginator = Paginator(queryset, page_size)
    page_obj = paginator.get_page(page)
    notifications = list(page_obj.object_list)

    unread_count = Notification.objects.filter(user=user, read_at__isnull=True).count()
    return {
        "groups": _group_notifications_by_date(notifications),
        "unread_count": unread_count,
        "pagination": {
            "page": page_obj.number,
            "page_size": page_size,
            "total_count": paginator.count,
            "total_pages": paginator.num_pages,
            "has_next": page_obj.has_next(),
            "has_previous": page_obj.has_previous(),
        },
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

    from apps.notifications.models import NotificationSettings

    user_ids = [receiver.user_id for receiver, _ in nearby_receivers]
    settings_by_user = {
        settings_obj.user_id: settings_obj
        for settings_obj in NotificationSettings.objects.filter(user_id__in=user_ids)
    }

    notifications = []
    for receiver, distance_m in nearby_receivers:
        settings_obj = settings_by_user.get(receiver.user_id)
        if settings_obj is not None:
            if not settings_obj.push_enabled or not settings_obj.alert_new_food_nearby:
                continue
        # No settings row yet → defaults allow alerts
        notifications.append(
            Notification(
                user=receiver.user,
                type="NEW_FOOD_NEARBY",
                title=f"{food.name} near you!",
                body=f"{restaurant.name} just posted it nearby.",
                payload={
                    "food_id": str(food.id),
                    "restaurant_id": str(restaurant.id),
                    "food_name": food.name,
                    "distance_km": round(distance_m / 1000, 1),
                },
            )
        )
    if not notifications:
        return 0
    Notification.objects.bulk_create(notifications)
    return len(notifications)
