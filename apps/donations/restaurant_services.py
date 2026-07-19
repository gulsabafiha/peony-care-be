from __future__ import annotations

import time
from collections import defaultdict
from datetime import date, datetime, timedelta

from django.db import transaction
from django.db.models import Count, Q, Sum

from apps.accounts.models import RestaurantProfile, User
from apps.claims.models import FoodClaim
from apps.common.choices import (
    ClaimStatus,
    ClosedReason,
    FoodStatus,
    ListStatus,
    RecurrenceType,
    SponsorshipType,
)
from apps.common.exceptions import PeonyAPIException
from apps.common.geocoding import extract_postal_code, resolve_restaurant_coordinates
from apps.common.phone import normalize_phone_e164
from apps.common.timezone_utils import (
    SGT,
    WEEKDAY_LABELS,
    format_day_label,
    format_pickup_window,
    format_relative_ago,
    now_sgt,
    today_sgt,
    week_bounds_sgt,
)
from apps.donations.models import FoodItem
from apps.notifications.models import Notification


def get_restaurant_profile(user: User) -> RestaurantProfile:
    try:
        return user.restaurant_profile
    except RestaurantProfile.DoesNotExist as exc:
        raise PeonyAPIException(
            code="PROFILE_NOT_FOUND",
            message="Restaurant profile not found.",
            http_status=404,
        ) from exc


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


def _donation_day(food: FoodItem) -> date:
    if food.closed_at:
        return food.closed_at.astimezone(SGT).date()
    return food.pickup_end.astimezone(SGT).date()


def _serialize_restaurant_donation(food: FoodItem, include_claims: bool = False) -> dict:
    percent = _percent_claimed(food)
    is_done = (
        food.status == FoodStatus.FULLY_CLAIMED
        or food.quantity_available <= 0
        or percent >= 100
    )
    is_sponsored = food.sponsorship_type != SponsorshipType.DIRECT
    paused_ago = None
    if food.list_status == ListStatus.INACTIVE and food.closed_at:
        paused_ago = f"paused {format_relative_ago(food.closed_at)}"

    data = {
        "id": str(food.id),
        "name": food.name,
        "description": food.description,
        "category": food.category,
        "unit": food.unit,
        "photo_url": food.photo_url,
        "quantity_original": food.quantity_original,
        "quantity_available": food.quantity_available,
        "quantity_claimed": food.quantity_claimed,
        "claims_progress_label": f"{food.quantity_claimed} of {food.quantity_original} claimed",
        "percent_claimed": percent,
        "is_done": is_done,
        "status": food.status,
        "list_status": food.list_status,
        "pickup_start": food.pickup_start.isoformat(),
        "pickup_end": food.pickup_end.isoformat(),
        "pickup_window": format_pickup_window(food.pickup_start, food.pickup_end),
        "recurrence_type": food.recurrence_type,
        "recurrence_days": food.recurrence_days or [],
        "recurrence_label": _recurrence_label(food.recurrence_type, food.recurrence_days or []),
        "sponsorship_type": food.sponsorship_type,
        "sponsor_display_name": food.sponsor_display_name or None,
        "is_sponsored": is_sponsored,
        "closed_at": food.closed_at.isoformat() if food.closed_at else None,
        "closed_reason": food.closed_reason or None,
        "paused_ago": paused_ago,
        "expired_count": _expired_count(food),
        "unclaimed_count": _unclaimed_count(food),
        "food_qr_data": food.food_qr_data,
        "food_qr_image_url": food.food_qr_image_url or None,
        "claims_count": food.claims.count(),
        "created_at": food.created_at.isoformat(),
    }
    if include_claims:
        data["claims"] = [
            {
                "id": str(claim.id),
                "receiver_name": claim.receiver.receiver_profile.display_name,
                "claimed_at": claim.claimed_at.isoformat(),
                "status": claim.status,
            }
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
) -> list[dict]:
    buckets: dict[date, list[FoodItem]] = defaultdict(list)
    for food in foods:
        buckets[_donation_day(food)].append(food)

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
    foods = FoodItem.objects.filter(restaurant=restaurant)
    claims = FoodClaim.objects.filter(restaurant=restaurant, status=ClaimStatus.CLAIMED)

    now = now_sgt()
    today = today_sgt()
    yesterday = today - timedelta(days=1)
    year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    week_start, week_end = week_bounds_sgt(today)
    prev_week_start = week_start - timedelta(days=7)

    total_original = foods.aggregate(total=Sum("quantity_original"))["total"] or 0
    total_claimed = claims.count()
    lifetime_claim_rate = round((total_claimed / total_original) * 100) if total_original else 0

    active_foods = list(
        foods.filter(list_status=ListStatus.ACTIVE, pickup_end__gt=now).order_by("pickup_end")
    )
    today_active = [food for food in active_foods if _donation_day(food) == today]
    if not today_active:
        today_active = active_foods

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
        created_at__gte=datetime.combine(week_start, datetime.min.time(), tzinfo=now.tzinfo),
        created_at__lt=datetime.combine(week_end, datetime.min.time(), tzinfo=now.tzinfo),
    ).count()
    inactive_this_week = foods.filter(
        list_status=ListStatus.INACTIVE,
        closed_at__gte=datetime.combine(week_start, datetime.min.time(), tzinfo=now.tzinfo),
        closed_at__lt=datetime.combine(week_end, datetime.min.time(), tzinfo=now.tzinfo),
    ).count()
    if inactive_this_week == 0:
        inactive_this_week = foods.filter(list_status=ListStatus.INACTIVE).count()

    day_start = datetime.combine(yesterday, datetime.min.time(), tzinfo=SGT)
    day_end = datetime.combine(today, datetime.min.time(), tzinfo=SGT)
    yesterday_past = list(
        foods.filter(list_status=ListStatus.PAST)
        .filter(
            Q(closed_at__gte=day_start, closed_at__lt=day_end)
            | Q(closed_at__isnull=True, pickup_end__gte=day_start, pickup_end__lt=day_end)
        )
        .order_by("-pickup_end")[:10]
    )

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
    if yesterday_past:
        active_groups.append(
            {
                "key": yesterday.isoformat(),
                "label": "Yesterday",
                "date": yesterday.isoformat(),
                "listings_count": len(yesterday_past),
                "portions": sum(food.quantity_original for food in yesterday_past),
                "fed": sum(food.quantity_claimed for food in yesterday_past),
                "items": [_serialize_restaurant_donation(food) for food in yesterday_past],
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
            "active_count": len(active_foods),
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
        "active_count": len(active_foods),
        "claimed_today": claimed_today,
        "today_listings": [_serialize_restaurant_donation(food) for food in today_active[:10]],
    }


def list_donations(user: User, status: str = "active") -> dict:
    restaurant = get_restaurant_profile(user)
    queryset = FoodItem.objects.filter(restaurant=restaurant)
    today = today_sgt()
    week_start, week_end = week_bounds_sgt(today)

    counts = queryset.aggregate(
        active_count=Count("id", filter=Q(list_status=ListStatus.ACTIVE)),
        past_count=Count("id", filter=Q(list_status=ListStatus.PAST)),
        inactive_count=Count("id", filter=Q(list_status=ListStatus.INACTIVE)),
    )

    if status == "active":
        foods = list(queryset.filter(list_status=ListStatus.ACTIVE).order_by("pickup_end"))
        groups = _group_donations(foods, today=today, for_past=False)
        selected_count = counts["active_count"]
        subtitle = None
        meals_this_week = None
    elif status == "past":
        foods = list(queryset.filter(list_status=ListStatus.PAST).order_by("-pickup_end"))
        groups = _group_donations(foods, today=today, for_past=True)
        selected_count = counts["past_count"]
        meals_this_week = (
            FoodClaim.objects.filter(
                restaurant=restaurant,
                status=ClaimStatus.CLAIMED,
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
            message="Status must be active, past, or inactive.",
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


@transaction.atomic
def create_donation(user: User, data: dict) -> dict:
    restaurant = get_restaurant_profile(user)

    now = now_sgt()
    if data["pickup_end"] <= now:
        raise PeonyAPIException(
            code="INVALID_PICKUP_WINDOW",
            message="Pickup end must be in the future.",
            http_status=400,
        )

    recurrence_type = data.get("recurrence_type", RecurrenceType.NONE)
    recurrence_days = _validate_recurrence(recurrence_type, data.get("recurrence_days"))

    food = FoodItem.objects.create(
        restaurant=restaurant,
        name=data["name"],
        description=data.get("description", ""),
        category=data["category"],
        unit=data.get("unit", "pack"),
        photo_url=data.get("photo_url", ""),
        quantity_original=data["quantity"],
        quantity_available=data["quantity"],
        quantity_claimed=0,
        status=FoodStatus.AVAILABLE,
        list_status=ListStatus.ACTIVE,
        pickup_start=data["pickup_start"],
        pickup_end=data["pickup_end"],
        recurrence_type=recurrence_type,
        recurrence_days=recurrence_days,
    )
    food.food_qr_data = _generate_qr_data(food)
    food.save(update_fields=["food_qr_data", "updated_at"])

    restaurant.total_food_shared += data["quantity"]
    restaurant.save(update_fields=["total_food_shared"])

    result = _serialize_restaurant_donation(food)
    result["estimated_reach"] = data["quantity"] * 3
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

    if food.claims.exists():
        raise PeonyAPIException(
            code="DONATION_HAS_CLAIMS",
            message="Cannot edit a donation that already has claims.",
            http_status=409,
        )

    if food.list_status != ListStatus.ACTIVE:
        raise PeonyAPIException(
            code="DONATION_NOT_EDITABLE",
            message="Only active donations can be edited.",
            http_status=409,
        )

    for field in ("name", "description", "category", "unit", "photo_url"):
        if field in data:
            setattr(food, field, data[field])

    if "quantity" in data:
        food.quantity_original = data["quantity"]
        food.quantity_available = data["quantity"]

    if "pickup_start" in data:
        food.pickup_start = data["pickup_start"]
    if "pickup_end" in data:
        food.pickup_end = data["pickup_end"]

    if "recurrence_type" in data or "recurrence_days" in data:
        recurrence_type = data.get("recurrence_type", food.recurrence_type)
        recurrence_days = data.get("recurrence_days", food.recurrence_days)
        food.recurrence_type = recurrence_type
        food.recurrence_days = _validate_recurrence(recurrence_type, recurrence_days)

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
    food.closed_at = now_sgt()
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

    if food.pickup_end <= now_sgt():
        raise PeonyAPIException(
            code="PICKUP_WINDOW_EXPIRED",
            message="Cannot reactivate — pickup window has ended.",
            http_status=410,
        )

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

    if food.list_status != ListStatus.INACTIVE:
        raise PeonyAPIException(
            code="DONATION_NOT_INACTIVE",
            message="Only inactive donations can be deleted.",
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


def get_restaurant_profile_data(user: User) -> dict:
    restaurant = get_restaurant_profile(user)
    return _serialize_restaurant_profile(restaurant)


def update_restaurant_profile_data(user: User, data: dict) -> dict:
    restaurant = get_restaurant_profile(user)

    profile_fields = (
        "name",
        "contact_name",
        "contact_email",
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
    return _serialize_restaurant_profile(restaurant)


def get_public_restaurant(restaurant_id: str) -> dict:
    try:
        restaurant = RestaurantProfile.objects.get(id=restaurant_id)
    except RestaurantProfile.DoesNotExist as exc:
        raise PeonyAPIException(
            code="RESTAURANT_NOT_FOUND",
            message="Restaurant not found.",
            http_status=404,
        ) from exc
    return _serialize_restaurant_profile(restaurant, public=True)


def _serialize_restaurant_profile(restaurant: RestaurantProfile, public: bool = False) -> dict:
    data = {
        "id": str(restaurant.id),
        "name": restaurant.name,
        "address": restaurant.address,
        "postal_code": restaurant.postal_code,
        "latitude": float(restaurant.latitude),
        "longitude": float(restaurant.longitude),
        "opening_hours": restaurant.opening_hours,
        "about": restaurant.about,
        "photo_url": restaurant.photo_url,
        "is_verified": restaurant.is_verified,
        "total_food_shared": restaurant.total_food_shared,
        "initials": _initials(restaurant.name),
    }
    if not public:
        data.update(
            {
                "uen": restaurant.uen,
                "contact_name": restaurant.contact_name,
                "contact_email": restaurant.contact_email,
                "contact_phone": restaurant.contact_phone,
                "is_approved": restaurant.is_approved,
            }
        )
    return data
