from __future__ import annotations

import time
from collections import defaultdict
from datetime import date, datetime, timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q, Sum

from apps.accounts.models import ReceiverProfile, RestaurantProfile, User
from apps.claims.models import FoodClaim
from apps.common.address import derive_area_label
from apps.common.choices import (
    COUNTED_CLAIM_STATUSES,
    ClosedReason,
    FoodCategory,
    FoodStatus,
    ListStatus,
    RecurrenceType,
    SponsorshipType,
)
from apps.common.exceptions import PeonyAPIException
from apps.common.geo import haversine_distance_m
from apps.common.geocoding import extract_postal_code, resolve_restaurant_coordinates
from apps.common.phone import normalize_phone_e164
from apps.common.timezone_utils import (
    WEEKDAY_LABELS,
    bounding_box,
    day_bounds_in,
    format_countdown_until,
    format_day_label,
    format_pickup_window,
    format_relative_ago,
    interpret_wallclock_in_tz,
    now_in,
    timezone_for_restaurant,
    to_local_iso,
    today_in,
    week_bounds_in,
)
from apps.common.uploads import (
    delete_stored_photo,
    save_food_item_photo,
    save_restaurant_profile_photo,
)
from apps.donations.category_units import format_quantity_unit, resolve_unit
from apps.donations.models import FoodItem
from apps.notifications.models import Notification
from apps.notifications.services import notify_nearby_receivers_of_new_food


def get_restaurant_profile(user: User) -> RestaurantProfile:
    try:
        return user.restaurant_profile
    except RestaurantProfile.DoesNotExist as exc:
        raise PeonyAPIException(
            code="PROFILE_NOT_FOUND",
            message="Restaurant profile not found.",
            http_status=404,
        ) from exc


def resolve_available_day_window(tz, pickup_start=None) -> tuple:
    """Listings are always today, available until local midnight."""
    today = today_in(tz)
    if pickup_start is not None:
        submitted = interpret_wallclock_in_tz(pickup_start, tz)
        if submitted.date() != today:
            raise PeonyAPIException(
                code="INVALID_AVAILABLE_DATE",
                message="Food can only be posted for today.",
                http_status=400,
            )
    return day_bounds_in(today, tz=tz)


def _generate_qr_data(food: FoodItem) -> str:
    return f"{food.id}|{food.restaurant_id}|{int(time.time())}"


def _initials(name: str) -> str:
    parts = [part for part in name.strip().split() if part]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0][:2].upper()
    return "".join(part[0].upper() for part in parts[:2])


def _validate_recurrence(recurrence_type: str, recurrence_days: list | None) -> list[int]:
    days = recurrence_days or []
    if recurrence_type == RecurrenceType.NONE:
        return []
    if recurrence_type == RecurrenceType.DAILY:
        return list(range(7))
    if recurrence_type == RecurrenceType.CUSTOM:
        if not days:
            raise PeonyAPIException(
                code="INVALID_RECURRENCE",
                message="recurrence_days is required for CUSTOM recurrence.",
                http_status=400,
            )
        normalized: list[int] = []
        for day in days:
            try:
                value = int(day)
            except (TypeError, ValueError) as exc:
                raise PeonyAPIException(
                    code="INVALID_RECURRENCE",
                    message="recurrence_days must be integers 0–6 (Mon–Sun).",
                    http_status=400,
                ) from exc
            if value < 0 or value > 6:
                raise PeonyAPIException(
                    code="INVALID_RECURRENCE",
                    message="recurrence_days must be integers 0–6 (Mon–Sun).",
                    http_status=400,
                )
            if value not in normalized:
                normalized.append(value)
        return sorted(normalized)
    raise PeonyAPIException(
        code="INVALID_RECURRENCE",
        message="recurrence_type must be NONE, DAILY, or CUSTOM.",
        http_status=400,
    )


def _recurrence_label(recurrence_type: str, recurrence_days: list) -> str | None:
    if recurrence_type == RecurrenceType.NONE:
        return None
    if recurrence_type == RecurrenceType.DAILY:
        return "Daily"
    labels = [WEEKDAY_LABELS[day] for day in recurrence_days if 0 <= day <= 6]
    return ", ".join(labels) if labels else None


def _recurrence_badge(recurrence_type: str, recurrence_days: list) -> str | None:
    label = _recurrence_label(recurrence_type, recurrence_days)
    if not label:
        return None
    if recurrence_type == RecurrenceType.DAILY:
        return "Repeats daily"
    return f"Repeats {label}"


def _recurrence_schedule_summary(food: FoodItem) -> str | None:
    if food.recurrence_type == RecurrenceType.NONE:
        return None
    if food.recurrence_type == RecurrenceType.DAILY:
        return "Auto-posts every day · next tomorrow"
    days = _recurrence_label(food.recurrence_type, food.recurrence_days or [])
    return f"Auto-posts on {days}"


def _donation_source(food: FoodItem) -> dict:
    if food.sponsorship_type != SponsorshipType.DIRECT:
        sponsor = food.sponsor_display_name or "a donor"
        return {
            "type": "SPONSORED",
            "label": "Sponsored",
            "detail": f"by {sponsor}",
            "display": f"Sponsored by {sponsor}",
        }
    detail = food.source_note or "Surplus from today's service."
    return {
        "type": "SELF",
        "label": "Self-donated",
        "detail": detail,
        "display": f"Self-donated: {detail}",
    }


def _claim_status_label(status: str) -> str:
    if status == "COLLECTED":
        return "Collected"
    if status == "NO_SHOW":
        return "No-show"
    return "Pending"


def _serialize_claim(claim: FoodClaim) -> dict:
    return {
        "id": str(claim.id),
        "receiver_name": claim.receiver.receiver_profile.display_name,
        "claimed_at": claim.claimed_at.isoformat(),
        "collected_at": claim.collected_at.isoformat() if claim.collected_at else None,
        "no_show_at": claim.no_show_at.isoformat() if claim.no_show_at else None,
        "status": claim.status,
        "status_label": _claim_status_label(claim.status),
        "can_mark_collected": claim.status == "CLAIMED",
        "can_mark_no_show": claim.status == "CLAIMED",
        "can_undo_no_show": claim.status == "NO_SHOW",
    }


def _percent_claimed(food: FoodItem) -> int:
    if food.quantity_original <= 0:
        return 0
    return round((food.quantity_claimed / food.quantity_original) * 100)


def _unclaimed_count(food: FoodItem) -> int:
    return max(food.quantity_original - food.quantity_claimed, 0)


def _expired_count(food: FoodItem) -> int:
    if food.closed_reason == ClosedReason.EXPIRED or food.status == FoodStatus.EXPIRED:
        return _unclaimed_count(food)
    return 0


def _donation_day(food: FoodItem, tz=None) -> date:
    zone = tz or timezone_for_restaurant(food.restaurant)
    return food.pickup_start.astimezone(zone).date()


def _serialize_restaurant_donation(food: FoodItem, include_claims: bool = False) -> dict:
    tz = timezone_for_restaurant(food.restaurant)
    percent = _percent_claimed(food)
    is_done = (
        food.status == FoodStatus.FULLY_CLAIMED
        or food.quantity_available <= 0
        or percent >= 100
    )
    is_sponsored = food.sponsorship_type != SponsorshipType.DIRECT
    paused_ago = None
    if food.list_status == ListStatus.INACTIVE and food.closed_at:
        paused_ago = f"paused {format_relative_ago(food.closed_at, tz=tz)}"
    quantity_left = food.quantity_available
    recurrence_days = food.recurrence_days or []

    data = {
        "id": str(food.id),
        "name": food.name,
        "description": food.description,
        "category": food.category,
        "category_label": _category_label(food.category),
        "unit": food.unit,
        "photo_url": food.photo_url,
        "quantity_original": food.quantity_original,
        "quantity_available": food.quantity_available,
        "quantity_claimed": food.quantity_claimed,
        "quantity_left": quantity_left,
        "quantity_left_label": f"{quantity_left} left to claim",
        "claims_progress_label": f"{food.quantity_claimed} of {food.quantity_original} claimed",
        "percent_claimed": percent,
        "is_done": is_done,
        "status": food.status,
        "list_status": food.list_status,
        "list_status_label": food.list_status.title() if food.list_status else None,
        "pickup_start": to_local_iso(food.pickup_start, tz),
        "pickup_end": to_local_iso(food.pickup_end, tz),
        "available_date": _donation_day(food, tz=tz).isoformat(),
        "pickup_anytime": True,
        "pickup_window": format_pickup_window(food.pickup_start, food.pickup_end, tz=tz),
        "time_until_close": format_countdown_until(food.pickup_end, tz=tz),
        "recurrence_type": food.recurrence_type,
        "recurrence_days": recurrence_days,
        "recurrence_label": _recurrence_label(food.recurrence_type, recurrence_days),
        "recurrence_badge": _recurrence_badge(food.recurrence_type, recurrence_days),
        "recurrence_schedule_summary": _recurrence_schedule_summary(food),
        "source_note": food.source_note or "",
        "source": _donation_source(food),
        "sponsorship_type": food.sponsorship_type,
        "sponsor_display_name": food.sponsor_display_name or None,
        "is_sponsored": is_sponsored,
        "closed_at": to_local_iso(food.closed_at, tz) if food.closed_at else None,
        "closed_reason": food.closed_reason or None,
        "paused_ago": paused_ago,
        "expired_count": _expired_count(food),
        "unclaimed_count": _unclaimed_count(food),
        "food_qr_data": food.food_qr_data,
        "food_qr_image_url": food.food_qr_image_url or None,
        "claims_count": food.claims.count(),
        "created_at": food.created_at.isoformat(),
        "actions": {
            "can_edit": food.list_status == ListStatus.ACTIVE,
            "can_pause": food.list_status == ListStatus.ACTIVE,
            "can_delete": food.list_status in (ListStatus.ACTIVE, ListStatus.INACTIVE),
            "can_reactivate": food.list_status == ListStatus.INACTIVE,
        },
    }
    if include_claims:
        data["claims"] = [
            _serialize_claim(claim)
            for claim in food.claims.select_related("receiver__receiver_profile").order_by(
                "-claimed_at"
            )
        ]
    return data


def _unread_alerts_count(user: User) -> int:
    return Notification.objects.filter(user=user, read_at__isnull=True).count()


def _week_over_week_pct(this_week: int, last_week: int) -> int:
    if last_week <= 0:
        return 100 if this_week > 0 else 0
    return round(((this_week - last_week) / last_week) * 100)


def _group_donations(
    foods: list[FoodItem],
    *,
    today: date,
    for_past: bool = False,
    tz=None,
) -> list[dict]:
    buckets: dict[date, list[FoodItem]] = defaultdict(list)
    for food in foods:
        buckets[_donation_day(food, tz=tz)].append(food)

    groups = []
    for day in sorted(buckets.keys(), reverse=True):
        items = buckets[day]
        serialized = [_serialize_restaurant_donation(food) for food in items]
        if for_past:
            groups.append(
                {
                    "key": day.isoformat(),
                    "label": format_day_label(day, today=today),
                    "date": day.isoformat(),
                    "completed_count": len(items),
                    "fed": sum(food.quantity_claimed for food in items),
                    "items": serialized,
                }
            )
        else:
            groups.append(
                {
                    "key": day.isoformat(),
                    "label": format_day_label(day, today=today),
                    "date": day.isoformat(),
                    "listings_count": len(items),
                    "portions": sum(food.quantity_original for food in items),
                    "fed": sum(food.quantity_claimed for food in items),
                    "items": serialized,
                }
            )
    return groups


def get_dashboard(user: User) -> dict:
    restaurant = get_restaurant_profile(user)
    from apps.donations.recurrence_services import ensure_recurring_donations_posted

    ensure_recurring_donations_posted(restaurant=restaurant)
    tz = timezone_for_restaurant(restaurant)
    foods = FoodItem.objects.filter(restaurant=restaurant).select_related("restaurant")
    claims = FoodClaim.objects.filter(
        restaurant=restaurant,
        status__in=COUNTED_CLAIM_STATUSES,
    )

    now = now_in(tz)
    today = today_in(tz)
    year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    week_start, week_end = week_bounds_in(today, tz=tz)
    prev_week_start = week_start - timedelta(days=7)

    total_original = foods.aggregate(total=Sum("quantity_original"))["total"] or 0
    total_claimed = claims.count()
    lifetime_claim_rate = round((total_claimed / total_original) * 100) if total_original else 0

    day_start, day_end = day_bounds_in(today, tz=tz)
    today_active = list(
        foods.filter(
            list_status=ListStatus.ACTIVE,
            pickup_end__gt=now,
            pickup_start__gte=day_start,
            pickup_start__lt=day_end,
        ).order_by("pickup_end")
    )

    today_original = sum(food.quantity_original for food in today_active) or 0
    today_claimed_qty = (
        claims.filter(claim_date=today).aggregate(total=Sum("quantity_claimed"))["total"] or 0
    )
    today_claim_rate = (
        round((today_claimed_qty / today_original) * 100) if today_original else lifetime_claim_rate
    )

    this_week_meals = (
        claims.filter(claim_date__gte=week_start, claim_date__lt=week_end).aggregate(
            total=Sum("quantity_claimed")
        )["total"]
        or 0
    )
    last_week_meals = (
        claims.filter(claim_date__gte=prev_week_start, claim_date__lt=week_start).aggregate(
            total=Sum("quantity_claimed")
        )["total"]
        or 0
    )
    this_week_donations = foods.filter(
        created_at__gte=datetime.combine(week_start, datetime.min.time(), tzinfo=tz),
        created_at__lt=datetime.combine(week_end, datetime.min.time(), tzinfo=tz),
    ).count()
    inactive_this_week = foods.filter(
        list_status=ListStatus.INACTIVE,
        closed_at__gte=datetime.combine(week_start, datetime.min.time(), tzinfo=tz),
        closed_at__lt=datetime.combine(week_end, datetime.min.time(), tzinfo=tz),
    ).count()
    if inactive_this_week == 0:
        inactive_this_week = foods.filter(list_status=ListStatus.INACTIVE).count()

    active_groups = []
    if today_active:
        active_groups.append(
            {
                "key": today.isoformat(),
                "label": "Today",
                "date": today.isoformat(),
                "listings_count": len(today_active),
                "portions": sum(food.quantity_original for food in today_active),
                "fed": sum(food.quantity_claimed for food in today_active),
                "items": [_serialize_restaurant_donation(food) for food in today_active[:10]],
            }
        )

    claimed_today = claims.filter(claim_date=today).count()
    week_over_week_pct = _week_over_week_pct(this_week_meals, last_week_meals)

    return {
        "restaurant": {
            "id": str(restaurant.id),
            "name": restaurant.name,
            "photo_url": restaurant.photo_url or None,
            "initials": _initials(restaurant.name),
        },
        "unread_alerts_count": _unread_alerts_count(user),
        "impact": {
            "lives_impacted": total_claimed,
            "donations_this_year": foods.filter(created_at__gte=year_start).count(),
            "week_over_week_pct": week_over_week_pct,
        },
        "today": {
            "active_count": len(today_active),
            "claimed_today": claimed_today,
            "claim_rate_pct": today_claim_rate,
        },
        "this_week": {
            "donations": this_week_donations,
            "meals": this_week_meals,
            "inactive_count": inactive_this_week,
        },
        "active_donations": {
            "groups": active_groups,
        },
        # Backward-compatible flat fields
        "lives_impacted": total_claimed,
        "donations_this_year": foods.filter(created_at__gte=year_start).count(),
        "claim_rate_pct": today_claim_rate,
        "active_count": len(today_active),
        "claimed_today": claimed_today,
        "today_listings": [_serialize_restaurant_donation(food) for food in today_active[:10]],
    }


def list_donations(user: User, status: str = "active") -> dict:
    restaurant = get_restaurant_profile(user)
    from apps.donations.recurrence_services import ensure_recurring_donations_posted

    ensure_recurring_donations_posted(restaurant=restaurant)
    tz = timezone_for_restaurant(restaurant)
    queryset = FoodItem.objects.filter(restaurant=restaurant).select_related("restaurant")
    today = today_in(tz)
    week_start, week_end = week_bounds_in(today, tz=tz)

    counts = queryset.aggregate(
        active_count=Count("id", filter=Q(list_status=ListStatus.ACTIVE)),
        past_count=Count("id", filter=Q(list_status=ListStatus.PAST)),
        inactive_count=Count("id", filter=Q(list_status=ListStatus.INACTIVE)),
    )

    if status == "active":
        foods = list(queryset.filter(list_status=ListStatus.ACTIVE).order_by("pickup_end"))
        groups = _group_donations(foods, today=today, for_past=False, tz=tz)
        selected_count = counts["active_count"]
        subtitle = None
        meals_this_week = None
    elif status in ("past", "expired"):
        foods = list(queryset.filter(list_status=ListStatus.PAST).order_by("-pickup_end"))
        groups = _group_donations(foods, today=today, for_past=True, tz=tz)
        selected_count = counts["past_count"]
        meals_this_week = (
            FoodClaim.objects.filter(
                restaurant=restaurant,
                status__in=COUNTED_CLAIM_STATUSES,
                claim_date__gte=week_start,
                claim_date__lt=week_end,
            ).aggregate(total=Sum("quantity_claimed"))["total"]
            or 0
        )
        subtitle = f"{meals_this_week} meals donated this week."
    elif status == "inactive":
        foods = list(
            queryset.filter(list_status=ListStatus.INACTIVE).order_by(
                "-closed_at",
                "-updated_at",
            )
        )
        groups = (
            [
                {
                    "key": "inactive",
                    "label": "Inactive",
                    "date": None,
                    "listings_count": len(foods),
                    "portions": sum(food.quantity_original for food in foods),
                    "fed": sum(food.quantity_claimed for food in foods),
                    "items": [_serialize_restaurant_donation(food) for food in foods],
                }
            ]
            if foods
            else []
        )
        selected_count = counts["inactive_count"]
        subtitle = "paused early — reactivate or remove."
        meals_this_week = None
    else:
        raise PeonyAPIException(
            code="INVALID_STATUS",
            message="Status must be active, past, expired, or inactive.",
            http_status=400,
        )

    return {
        "summary": {
            "active_count": counts["active_count"],
            "past_count": counts["past_count"],
            "inactive_count": counts["inactive_count"],
            "selected_count": selected_count,
            "meals_this_week": meals_this_week,
            "subtitle": subtitle,
        },
        "groups": groups,
    }


def _category_label(category: str) -> str:
    try:
        return FoodCategory(category).label
    except ValueError:
        return category.title()


def _nearby_receivers(
    restaurant: RestaurantProfile,
) -> list[tuple[ReceiverProfile, float]]:
    """Return (receiver_profile, distance_m) for receivers within browse range."""
    radius_km = float(settings.DEFAULT_BROWSE_RADIUS_KM)
    lat = float(restaurant.latitude)
    lng = float(restaurant.longitude)
    min_lat, max_lat, min_lng, max_lng = bounding_box(lat, lng, radius_km)

    candidates = ReceiverProfile.objects.filter(
        location_services_enabled=True,
        latitude__isnull=False,
        longitude__isnull=False,
        latitude__gte=min_lat,
        latitude__lte=max_lat,
        longitude__gte=min_lng,
        longitude__lte=max_lng,
        user__is_active=True,
    ).select_related("user")

    radius_m = radius_km * 1000
    nearby: list[tuple[ReceiverProfile, float]] = []
    for receiver in candidates:
        distance_m = haversine_distance_m(
            lat,
            lng,
            float(receiver.latitude),
            float(receiver.longitude),
        )
        receiver_radius_m = float(receiver.browse_radius_km or radius_km) * 1000
        # Must be within the default search area and the receiver's own browse radius.
        if distance_m <= radius_m and distance_m <= receiver_radius_m:
            nearby.append((receiver, distance_m))
    return nearby


def _estimate_receiver_reach(restaurant: RestaurantProfile) -> dict:
    radius_km = float(settings.DEFAULT_BROWSE_RADIUS_KM)
    nearby = _nearby_receivers(restaurant)
    return {
        "count": len(nearby),
        "radius_km": int(radius_km) if radius_km.is_integer() else radius_km,
    }


def _build_post_success_payload(
    food: FoodItem,
    restaurant: RestaurantProfile,
    request=None,
    nearby_count: int | None = None,
) -> dict:
    if nearby_count is None:
        reach = _estimate_receiver_reach(restaurant)
        radius = reach["radius_km"]
        count = reach["count"]
    else:
        radius_km = float(settings.DEFAULT_BROWSE_RADIUS_KM)
        radius = int(radius_km) if radius_km.is_integer() else radius_km
        count = nearby_count
    category_label = _category_label(food.category)
    unit = format_quantity_unit(food.quantity_original, food.unit)
    address_short = restaurant.address.split(",")[0].strip() if restaurant.address else ""

    return {
        "success_message": "Donation posted",
        "success_subtitle": "Receivers nearby will be notified within seconds.",
        "estimated_reach": count,
        "estimated_reach_radius_km": radius,
        "estimated_reach_label": (
            f"~{count} receivers within {radius} km will see this."
        ),
        "restaurant": {
            "id": str(restaurant.id),
            "name": restaurant.name,
            "address": restaurant.address,
            "address_short": address_short,
        },
        "summary": {
            "title": food.name,
            "subtitle": f"{unit} · {category_label}",
            "category_label": category_label,
            "pickup_window_label": format_pickup_window(
                food.pickup_start,
                food.pickup_end,
                tz=timezone_for_restaurant(restaurant),
            ),
            "location_label": restaurant.name,
            "address_short": address_short,
        },
        "photo_url": _absolute_photo_url(request, food.photo_url or None),
    }


@transaction.atomic
def create_donation(user: User, data: dict, request=None) -> dict:
    restaurant = get_restaurant_profile(user)
    tz = timezone_for_restaurant(restaurant)
    recurrence_type = data.get("recurrence_type", RecurrenceType.NONE)
    recurrence_days = _validate_recurrence(recurrence_type, data.get("recurrence_days"))

    from apps.donations.recurrence_services import next_scheduled_day, should_post_on

    today = today_in(tz)
    if recurrence_type == RecurrenceType.CUSTOM and not should_post_on(
        recurrence_type, recurrence_days, today
    ):
        # Today is not a selected weekday. First listing opens on the next one.
        pickup_start, pickup_end = day_bounds_in(
            next_scheduled_day(recurrence_days, today),
            tz=tz,
        )
    else:
        pickup_start, pickup_end = resolve_available_day_window(tz, data.get("pickup_start"))

    photo_url = data.get("photo_url", "") or ""
    uploaded_photo = data.get("photo")
    if uploaded_photo is not None:
        photo_url = save_food_item_photo(str(restaurant.id), uploaded_photo)

    food = FoodItem.objects.create(
        restaurant=restaurant,
        name=data["name"],
        description=data.get("description", ""),
        category=data["category"],
        unit=resolve_unit(data["category"], data.get("unit")),
        photo_url=photo_url,
        quantity_original=data["quantity"],
        quantity_available=data["quantity"],
        quantity_claimed=0,
        status=FoodStatus.AVAILABLE,
        list_status=ListStatus.ACTIVE,
        pickup_start=pickup_start,
        pickup_end=pickup_end,
        recurrence_type=recurrence_type,
        recurrence_days=recurrence_days,
        source_note=data.get("source_note", ""),
    )
    update_fields = ["food_qr_data", "updated_at"]
    food.food_qr_data = _generate_qr_data(food)
    if recurrence_type in (RecurrenceType.DAILY, RecurrenceType.CUSTOM):
        food.recurrence_series_id = food.id
        update_fields.append("recurrence_series_id")
    food.save(update_fields=update_fields)

    restaurant.total_food_shared += data["quantity"]
    restaurant.save(update_fields=["total_food_shared"])

    nearby = _nearby_receivers(restaurant)
    if pickup_start <= now_in(tz):
        notify_nearby_receivers_of_new_food(food, restaurant, nearby)

    result = _serialize_restaurant_donation(food)
    result.update(
        _build_post_success_payload(
            food,
            restaurant,
            request=request,
            nearby_count=len(nearby),
        )
    )
    return result


def get_donation(user: User, food_id: str) -> dict:
    restaurant = get_restaurant_profile(user)
    try:
        food = FoodItem.objects.get(id=food_id, restaurant=restaurant)
    except FoodItem.DoesNotExist as exc:
        raise PeonyAPIException(
            code="DONATION_NOT_FOUND",
            message="Donation not found.",
            http_status=404,
        ) from exc
    return _serialize_restaurant_donation(food, include_claims=True)


@transaction.atomic
def update_donation(user: User, food_id: str, data: dict) -> dict:
    restaurant = get_restaurant_profile(user)
    try:
        food = FoodItem.objects.select_for_update().get(id=food_id, restaurant=restaurant)
    except FoodItem.DoesNotExist as exc:
        raise PeonyAPIException(
            code="DONATION_NOT_FOUND",
            message="Donation not found.",
            http_status=404,
        ) from exc

    if food.list_status != ListStatus.ACTIVE:
        raise PeonyAPIException(
            code="DONATION_NOT_EDITABLE",
            message="Only active donations can be edited.",
            http_status=409,
        )

    has_claims = food.claims.exists()
    for field in ("name", "description", "category", "unit", "photo_url", "source_note"):
        if field in data:
            if has_claims and field in ("name", "category", "unit"):
                raise PeonyAPIException(
                    code="DONATION_HAS_CLAIMS",
                    message="Cannot change name, category, or unit after claims exist.",
                    http_status=409,
                )
            setattr(food, field, data[field])

    if "category" in data or "unit" in data:
        supplied = data.get("unit") if "unit" in data else food.unit
        food.unit = resolve_unit(food.category, supplied)

    if "quantity" in data:
        if data["quantity"] < food.quantity_claimed:
            raise PeonyAPIException(
                code="INVALID_QUANTITY",
                message="Quantity cannot be less than already claimed portions.",
                http_status=400,
            )
        food.quantity_original = data["quantity"]
        food.quantity_available = max(data["quantity"] - food.quantity_claimed, 0)
        if food.quantity_available <= 0:
            food.status = FoodStatus.FULLY_CLAIMED
        elif food.quantity_claimed > 0:
            food.status = FoodStatus.PARTIALLY_CLAIMED
        else:
            food.status = FoodStatus.AVAILABLE

    if "recurrence_type" in data or "recurrence_days" in data:
        recurrence_type = data.get("recurrence_type", food.recurrence_type)
        recurrence_days = data.get("recurrence_days", food.recurrence_days)
        food.recurrence_type = recurrence_type
        food.recurrence_days = _validate_recurrence(recurrence_type, recurrence_days)
        if recurrence_type in (RecurrenceType.DAILY, RecurrenceType.CUSTOM):
            if not food.recurrence_series_id:
                food.recurrence_series_id = food.id
        else:
            food.recurrence_series_id = None

    food.save()
    return _serialize_restaurant_donation(food)


@transaction.atomic
def close_donation(user: User, food_id: str) -> dict:
    restaurant = get_restaurant_profile(user)
    try:
        food = FoodItem.objects.select_for_update().get(id=food_id, restaurant=restaurant)
    except FoodItem.DoesNotExist as exc:
        raise PeonyAPIException(
            code="DONATION_NOT_FOUND",
            message="Donation not found.",
            http_status=404,
        ) from exc

    if food.list_status != ListStatus.ACTIVE:
        raise PeonyAPIException(
            code="DONATION_NOT_ACTIVE",
            message="Only active donations can be closed.",
            http_status=409,
        )

    food.list_status = ListStatus.INACTIVE
    food.closed_at = now_in(timezone_for_restaurant(restaurant))
    food.closed_reason = ClosedReason.MANUAL
    food.save(update_fields=["list_status", "closed_at", "closed_reason", "updated_at"])
    return _serialize_restaurant_donation(food)


@transaction.atomic
def reactivate_donation(user: User, food_id: str) -> dict:
    restaurant = get_restaurant_profile(user)
    try:
        food = FoodItem.objects.select_for_update().get(id=food_id, restaurant=restaurant)
    except FoodItem.DoesNotExist as exc:
        raise PeonyAPIException(
            code="DONATION_NOT_FOUND",
            message="Donation not found.",
            http_status=404,
        ) from exc

    if food.list_status != ListStatus.INACTIVE:
        raise PeonyAPIException(
            code="DONATION_NOT_INACTIVE",
            message="Only inactive donations can be reactivated.",
            http_status=409,
        )

    # Paused listings stay INACTIVE after local midnight (only ACTIVE ones
    # roll to PAST). Put the listing back on today's window so reactivate
    # works for any deactivated donation, including ones paused on a prior day.
    tz = timezone_for_restaurant(restaurant)
    if food.pickup_end <= now_in(tz):
        food.pickup_start, food.pickup_end = day_bounds_in(today_in(tz), tz=tz)

    food.list_status = ListStatus.ACTIVE
    food.closed_at = None
    food.closed_reason = ""
    if food.quantity_available > 0:
        food.status = (
            FoodStatus.AVAILABLE if food.quantity_claimed == 0 else FoodStatus.PARTIALLY_CLAIMED
        )
    food.save()
    return _serialize_restaurant_donation(food)


@transaction.atomic
def delete_donation(user: User, food_id: str) -> dict:
    restaurant = get_restaurant_profile(user)
    try:
        food = FoodItem.objects.get(id=food_id, restaurant=restaurant)
    except FoodItem.DoesNotExist as exc:
        raise PeonyAPIException(
            code="DONATION_NOT_FOUND",
            message="Donation not found.",
            http_status=404,
        ) from exc

    if food.list_status not in (ListStatus.ACTIVE, ListStatus.INACTIVE):
        raise PeonyAPIException(
            code="DONATION_NOT_DELETABLE",
            message="Only active or inactive donations can be deleted.",
            http_status=409,
        )

    food.delete()
    return {"message": "Donation deleted successfully."}


def get_approval_status(user: User) -> dict:
    restaurant = get_restaurant_profile(user)
    return {
        "is_approved": restaurant.is_approved,
        "is_verified": restaurant.is_verified,
        "submitted_at": restaurant.created_at.isoformat(),
        "approved_at": restaurant.approved_at.isoformat() if restaurant.approved_at else None,
    }


def get_restaurant_profile_data(user: User, request=None) -> dict:
    restaurant = get_restaurant_profile(user)
    return _serialize_restaurant_profile(restaurant, request=request)


def _format_opening_hours_text(
    opens_at,
    closes_at,
    open_days: list[int],
) -> str:
    if not opens_at or not closes_at:
        return ""
    open_label = opens_at.strftime("%I:%M %p").lstrip("0")
    close_label = closes_at.strftime("%I:%M %p").lstrip("0")
    if open_days and sorted(open_days) != list(range(7)):
        days = ", ".join(WEEKDAY_LABELS[day] for day in sorted(open_days) if 0 <= day <= 6)
        return f"{days} {open_label} – {close_label}"
    return f"{open_label} – {close_label}"


def _validate_open_days(open_days: list | None) -> list[int]:
    days = open_days or []
    normalized: list[int] = []
    for day in days:
        try:
            value = int(day)
        except (TypeError, ValueError) as exc:
            raise PeonyAPIException(
                code="INVALID_OPEN_DAYS",
                message="open_days must be integers 0–6 (Mon–Sun).",
                http_status=400,
            ) from exc
        if value < 0 or value > 6:
            raise PeonyAPIException(
                code="INVALID_OPEN_DAYS",
                message="open_days must be integers 0–6 (Mon–Sun).",
                http_status=400,
            )
        if value not in normalized:
            normalized.append(value)
    return sorted(normalized)


def update_restaurant_profile_data(user: User, data: dict, request=None) -> dict:
    restaurant = get_restaurant_profile(user)

    profile_fields = (
        "name",
        "contact_name",
        "contact_email",
        "cuisine",
        "opening_hours",
        "about",
        "photo_url",
    )
    for field in profile_fields:
        if field in data:
            setattr(restaurant, field, data[field])

    if "contact_phone" in data:
        phone = data["contact_phone"]
        restaurant.contact_phone = (
            normalize_phone_e164(phone) if phone and str(phone).strip() else ""
        )

    structured_hours_touched = False
    if "opens_at" in data:
        restaurant.opens_at = data["opens_at"]
        structured_hours_touched = True
    if "closes_at" in data:
        restaurant.closes_at = data["closes_at"]
        structured_hours_touched = True
    if "open_days" in data:
        restaurant.open_days = _validate_open_days(data["open_days"])
        structured_hours_touched = True

    if structured_hours_touched and "opening_hours" not in data:
        restaurant.opening_hours = _format_opening_hours_text(
            restaurant.opens_at,
            restaurant.closes_at,
            restaurant.open_days or [],
        )

    if data.get("remove_photo"):
        if restaurant.photo_url:
            delete_stored_photo(restaurant.photo_url)
        restaurant.photo_url = ""
    elif data.get("photo") is not None:
        if restaurant.photo_url:
            delete_stored_photo(restaurant.photo_url)
        restaurant.photo_url = save_restaurant_profile_photo(
            str(restaurant.id),
            data["photo"],
        )

    if "address" in data or "latitude" in data or "longitude" in data:
        address = data.get("address", restaurant.address)
        latitude = data.get("latitude")
        longitude = data.get("longitude")
        if "address" in data:
            restaurant.address = address
            restaurant.postal_code = extract_postal_code(address)
        lat, lng = resolve_restaurant_coordinates(
            address,
            latitude,
            longitude,
        )
        restaurant.latitude = lat
        restaurant.longitude = lng

    restaurant.save()
    return _serialize_restaurant_profile(restaurant, request=request)


def get_public_restaurant(restaurant_id: str, request=None) -> dict:
    try:
        restaurant = RestaurantProfile.objects.select_related("user").get(id=restaurant_id)
    except RestaurantProfile.DoesNotExist as exc:
        raise PeonyAPIException(
            code="RESTAURANT_NOT_FOUND",
            message="Restaurant not found.",
            http_status=404,
        ) from exc
    return _serialize_restaurant_detail_page(restaurant, request=request, include_meals=True)


def build_restaurant_impact_stats(restaurant: RestaurantProfile) -> dict:
    """Lifetime FED / DONATIONS / CLAIM RATE for public + profile hub screens."""
    return _profile_hub_stats(restaurant)


def _absolute_photo_url(request, photo_url: str | None) -> str | None:
    if not photo_url:
        return None
    if photo_url.startswith("http://") or photo_url.startswith("https://"):
        return photo_url
    if request is None:
        return photo_url
    return request.build_absolute_uri(photo_url)


def _profile_hub_stats(restaurant: RestaurantProfile) -> dict:
    """Lifetime impact stats for profile hub + public details screens."""
    from apps.claims.review_services import restaurant_rating_stats

    people_fed = (
        FoodClaim.objects.filter(
            restaurant=restaurant,
            status__in=COUNTED_CLAIM_STATUSES,
        ).aggregate(total=Sum("quantity_claimed"))["total"]
        or 0
    )
    donations_count = FoodItem.objects.filter(restaurant=restaurant).count()
    total_original = (
        FoodItem.objects.filter(restaurant=restaurant).aggregate(
            total=Sum("quantity_original")
        )["total"]
        or 0
    )
    claim_rate_pct = round((people_fed / total_original) * 100) if total_original else None
    rating_stats = restaurant_rating_stats(restaurant.id)
    return {
        "people_fed": people_fed,
        "people_fed_label": "fed",
        "donations_count": donations_count,
        "donations_label": "donations",
        "claim_rate_pct": claim_rate_pct,
        "claim_rate_display": "—" if claim_rate_pct is None else f"{claim_rate_pct}%",
        "claim_rate_label": "claim rate",
        **rating_stats,
    }


def _hours_display(restaurant: RestaurantProfile) -> str:
    if restaurant.opening_hours:
        return restaurant.opening_hours
    return _format_opening_hours_text(
        restaurant.opens_at,
        restaurant.closes_at,
        restaurant.open_days or [],
    )


def _serialize_available_meal(food: FoodItem) -> dict:
    tz = timezone_for_restaurant(food.restaurant)
    is_sponsored = food.sponsorship_type != SponsorshipType.DIRECT
    title = food.name
    if is_sponsored:
        title = f"{food.name} · Sponsored"
    unit = food.unit or "pack"
    unit_label = format_quantity_unit(food.quantity_original, unit)
    sponsor = food.sponsor_display_name or None
    if is_sponsored and sponsor:
        subtitle = f"{unit_label} · by {sponsor}"
    else:
        subtitle = (
            f"{unit_label} · pickup anytime today"
            if _donation_day(food, tz=tz) == today_in(tz)
            else f"{unit_label} · pickup anytime"
        )
    return {
        "id": str(food.id),
        "name": food.name,
        "title": title,
        "subtitle": subtitle,
        "description": food.description,
        "category": food.category,
        "photo_url": food.photo_url or None,
        "quantity_available": food.quantity_available,
        "quantity_original": food.quantity_original,
        "quantity_left_label": f"{food.quantity_available} left",
        "unit": unit,
        "pickup_start": to_local_iso(food.pickup_start, tz),
        "pickup_end": to_local_iso(food.pickup_end, tz),
        "available_date": _donation_day(food, tz=tz).isoformat(),
        "pickup_anytime": True,
        "pickup_window": format_pickup_window(food.pickup_start, food.pickup_end, tz=tz),
        "sponsorship_type": food.sponsorship_type,
        "is_sponsored": is_sponsored,
        "sponsor_display_name": sponsor,
        "sponsor_initials": _initials(sponsor) if sponsor else None,
    }


def _serialize_restaurant_detail_page(
    restaurant: RestaurantProfile,
    *,
    request=None,
    include_meals: bool = False,
    lat: float | None = None,
    lng: float | None = None,
) -> dict:
    """Payload for screen 6.2 Rest Details (public + receiver)."""
    hub = _profile_hub_stats(restaurant)
    open_days = restaurant.open_days or []
    contact_phone = restaurant.contact_phone
    if not contact_phone and getattr(restaurant, "user", None):
        contact_phone = restaurant.user.phone_e164

    data = {
        "id": str(restaurant.id),
        "name": restaurant.name,
        "address": restaurant.address,
        "postal_code": restaurant.postal_code,
        "area_label": derive_area_label(restaurant.address),
        "latitude": float(restaurant.latitude),
        "longitude": float(restaurant.longitude),
        "cuisine": restaurant.cuisine,
        "about": restaurant.about,
        "opening_hours": _hours_display(restaurant),
        "opens_at": restaurant.opens_at.isoformat() if restaurant.opens_at else None,
        "closes_at": restaurant.closes_at.isoformat() if restaurant.closes_at else None,
        "open_days": open_days,
        "open_days_labels": [WEEKDAY_LABELS[day] for day in open_days if 0 <= day <= 6],
        "photo_url": _absolute_photo_url(request, restaurant.photo_url or None),
        "contact_phone": contact_phone or "",
        "is_verified": restaurant.is_verified,
        "verified_label": "Verified partner" if restaurant.is_verified else None,
        "initials": _initials(restaurant.name),
        "impact": {
            "people_fed": hub["people_fed"],
            "people_fed_label": hub["people_fed_label"],
            "donations_count": hub["donations_count"],
            "donations_label": hub["donations_label"],
            "claim_rate_pct": hub["claim_rate_pct"],
            "claim_rate_display": hub["claim_rate_display"],
            "claim_rate_label": hub["claim_rate_label"],
        },
        "people_fed": hub["people_fed"],
        "donations_count": hub["donations_count"],
        "claim_rate_pct": hub["claim_rate_pct"],
        "claim_rate_display": hub["claim_rate_display"],
        "rating": hub["rating"],
        "rating_display": hub["rating_display"],
        "review_count": hub["review_count"],
        "reviews_available": hub["reviews_available"],
        "reviews_label": hub["reviews_label"],
    }

    if lat is not None and lng is not None:
        distance_m = haversine_distance_m(
            lat,
            lng,
            float(restaurant.latitude),
            float(restaurant.longitude),
        )
        data["distance_km"] = round(distance_m / 1000, 1)

    if include_meals:
        now = now_in(timezone_for_restaurant(restaurant))
        foods = list(
            FoodItem.objects.filter(
                restaurant=restaurant,
                list_status=ListStatus.ACTIVE,
                quantity_available__gt=0,
                pickup_start__lte=now,
                pickup_end__gt=now,
            )
            .exclude(status=FoodStatus.EXPIRED)
            .order_by("pickup_start", "name")
        )
        data["available_meals"] = [_serialize_available_meal(food) for food in foods]
        data["active_meal_count"] = len(foods)
        data["available_now_label"] = (
            f"{len(foods)} item{'s' if len(foods) != 1 else ''}" if foods else "0 items"
        )

    return data


def _serialize_restaurant_profile(
    restaurant: RestaurantProfile,
    public: bool = False,
    request=None,
) -> dict:
    open_days = restaurant.open_days or []
    data = {
        "id": str(restaurant.id),
        "name": restaurant.name,
        "address": restaurant.address,
        "postal_code": restaurant.postal_code,
        "area_label": derive_area_label(restaurant.address),
        "latitude": float(restaurant.latitude),
        "longitude": float(restaurant.longitude),
        "cuisine": restaurant.cuisine,
        "opening_hours": restaurant.opening_hours,
        "opens_at": restaurant.opens_at.isoformat() if restaurant.opens_at else None,
        "closes_at": restaurant.closes_at.isoformat() if restaurant.closes_at else None,
        "open_days": open_days,
        "open_days_labels": [WEEKDAY_LABELS[day] for day in open_days if 0 <= day <= 6],
        "about": restaurant.about,
        "photo_url": _absolute_photo_url(request, restaurant.photo_url or None),
        "is_verified": restaurant.is_verified,
        "total_food_shared": restaurant.total_food_shared,
        "initials": _initials(restaurant.name),
    }
    if not public:
        hub = _profile_hub_stats(restaurant)
        data.update(
            {
                "uen": restaurant.uen,
                "uen_verified": True,
                "contact_name": restaurant.contact_name,
                "contact_email": restaurant.contact_email,
                "contact_phone": restaurant.contact_phone,
                "is_approved": restaurant.is_approved,
                "member_since": restaurant.created_at.astimezone(
                    timezone_for_restaurant(restaurant)
                ).strftime("%b %Y"),
                "hub": hub,
                "people_fed": hub["people_fed"],
                "donations_count": hub["donations_count"],
                "claim_rate_pct": hub["claim_rate_pct"],
                "claim_rate_display": hub["claim_rate_display"],
                "rating": hub["rating"],
                "rating_display": hub["rating_display"],
                "review_count": hub["review_count"],
            }
        )
    return data
