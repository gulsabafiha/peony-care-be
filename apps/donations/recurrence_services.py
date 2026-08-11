from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from uuid import UUID

from django.db import transaction
from django.db.models import Max

from apps.accounts.models import RestaurantProfile
from apps.common.choices import ClosedReason, FoodStatus, ListStatus, RecurrenceType
from apps.common.timezone_utils import now_in, timezone_for_restaurant, today_in
from apps.donations.models import FoodItem
from apps.notifications.services import notify_nearby_receivers_of_new_food

logger = logging.getLogger(__name__)


def _weekday_mon0(d: date) -> int:
    """Monday=0 … Sunday=6 (matches recurrence_days payload)."""
    return d.weekday()


def should_post_on(recurrence_type: str, recurrence_days: list | None, day: date) -> bool:
    if recurrence_type == RecurrenceType.DAILY:
        return True
    if recurrence_type == RecurrenceType.CUSTOM:
        days = recurrence_days or []
        return _weekday_mon0(day) in {int(d) for d in days}
    return False


def _local_pickup_window_for_day(
    template: FoodItem,
    target_day: date,
    tz,
) -> tuple[datetime, datetime]:
    start_local = template.pickup_start.astimezone(tz)
    end_local = template.pickup_end.astimezone(tz)
    spans_midnight = end_local.date() > start_local.date()

    new_start = datetime.combine(target_day, start_local.time(), tzinfo=tz)
    end_day = target_day + timedelta(days=1) if spans_midnight else target_day
    new_end = datetime.combine(end_day, end_local.time(), tzinfo=tz)

    if new_end <= new_start:
        new_end = new_start + (end_local - start_local)
    return new_start, new_end


def _series_has_listing_on(series_id: UUID, day: date, tz) -> bool:
    day_start = datetime.combine(day, time.min, tzinfo=tz)
    day_end = datetime.combine(day, time.max, tzinfo=tz)
    return FoodItem.objects.filter(
        recurrence_series_id=series_id,
        pickup_start__gte=day_start,
        pickup_start__lte=day_end,
    ).exists()


def _clone_donation_for_day(template: FoodItem, target_day: date) -> FoodItem | None:
    restaurant = template.restaurant
    tz = timezone_for_restaurant(restaurant)
    pickup_start, pickup_end = _local_pickup_window_for_day(template, target_day, tz)

    if pickup_end <= now_in(tz):
        return None

    from apps.donations.restaurant_services import _generate_qr_data, _nearby_receivers

    food = FoodItem.objects.create(
        restaurant=restaurant,
        name=template.name,
        description=template.description,
        category=template.category,
        unit=template.unit,
        photo_url=template.photo_url,
        quantity_original=template.quantity_original,
        quantity_available=template.quantity_original,
        quantity_claimed=0,
        status=FoodStatus.AVAILABLE,
        list_status=ListStatus.ACTIVE,
        pickup_start=pickup_start,
        pickup_end=pickup_end,
        recurrence_type=template.recurrence_type,
        recurrence_days=list(template.recurrence_days or []),
        recurrence_series_id=template.recurrence_series_id,
        source_note=template.source_note,
        sponsorship_type=template.sponsorship_type,
        individual_donor=template.individual_donor,
        sponsor_display_name=template.sponsor_display_name,
        meal_order_id=template.meal_order_id,
    )
    food.food_qr_data = _generate_qr_data(food)
    food.save(update_fields=["food_qr_data", "updated_at"])

    restaurant.total_food_shared += food.quantity_original
    restaurant.save(update_fields=["total_food_shared"])

    nearby = _nearby_receivers(restaurant)
    notify_nearby_receivers_of_new_food(food, restaurant, nearby)
    return food


def _archive_expired_listings(series_id: UUID, tz) -> None:
    now = now_in(tz)
    expired = FoodItem.objects.filter(
        recurrence_series_id=series_id,
        list_status=ListStatus.ACTIVE,
        pickup_end__lte=now,
    )
    for food in expired:
        food.list_status = ListStatus.PAST
        food.closed_at = now
        if food.quantity_available > 0:
            food.status = FoodStatus.EXPIRED
            food.closed_reason = ClosedReason.EXPIRED
        else:
            food.closed_reason = food.closed_reason or ClosedReason.FULLY_CLAIMED
        food.save(
            update_fields=[
                "list_status",
                "status",
                "closed_at",
                "closed_reason",
                "updated_at",
            ]
        )


@transaction.atomic
def _repost_series(series_id: UUID, target_day: date | None = None) -> FoodItem | None:
    latest = (
        FoodItem.objects.select_for_update()
        .select_related("restaurant", "individual_donor")
        .filter(recurrence_series_id=series_id)
        .order_by("-created_at")
        .first()
    )
    if not latest:
        return None

    if latest.recurrence_type not in (RecurrenceType.DAILY, RecurrenceType.CUSTOM):
        return None

    # Manual pause on the latest listing stops the series.
    if (
        latest.list_status == ListStatus.INACTIVE
        and latest.closed_reason == ClosedReason.MANUAL
    ):
        return None

    tz = timezone_for_restaurant(latest.restaurant)
    day = target_day or today_in(tz)
    _archive_expired_listings(series_id, tz)

    if not should_post_on(latest.recurrence_type, latest.recurrence_days, day):
        return None

    if _series_has_listing_on(series_id, day, tz):
        return None

    return _clone_donation_for_day(latest, day)


def ensure_recurring_donations_posted(
    *,
    restaurant: RestaurantProfile | None = None,
    target_day: date | None = None,
) -> list[FoodItem]:
    """
    Create today's listing for each active DAILY/CUSTOM series that needs one.

    Safe to call from API read paths and from a cron management command.
    """
    qs = FoodItem.objects.filter(
        recurrence_type__in=[RecurrenceType.DAILY, RecurrenceType.CUSTOM],
        recurrence_series_id__isnull=False,
    )
    if restaurant is not None:
        qs = qs.filter(restaurant=restaurant)

    series_ids = list(
        qs.values("recurrence_series_id")
        .annotate(latest=Max("created_at"))
        .values_list("recurrence_series_id", flat=True)
    )

    created: list[FoodItem] = []
    for series_id in series_ids:
        try:
            food = _repost_series(series_id, target_day=target_day)
        except Exception:
            logger.exception("Failed to auto-repost recurrence series %s", series_id)
            continue
        if food is not None:
            created.append(food)
    return created
