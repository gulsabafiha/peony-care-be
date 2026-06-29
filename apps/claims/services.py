from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from django.conf import settings
from django.db import transaction

from apps.accounts.models import User
from apps.claims.models import FoodClaim
from apps.common.choices import ClaimStatus, FoodStatus, ListStatus
from apps.common.exceptions import PeonyAPIException
from apps.common.geo import haversine_distance_m
from apps.common.timezone_utils import (
    format_pickup_window,
    next_midnight_sgt,
    now_sgt,
    today_sgt,
)
from apps.donations.models import FoodItem
from apps.notifications.models import Notification


def get_daily_limit_status(receiver: User) -> dict:
    used = FoodClaim.objects.filter(
        receiver=receiver,
        claim_date=today_sgt(),
        status=ClaimStatus.CLAIMED,
    ).count()
    limit = settings.DAILY_CLAIM_LIMIT
    return {
        "used": used,
        "limit": limit,
        "can_claim": used < limit,
        "resets_at": next_midnight_sgt().isoformat(),
    }


def _validate_qr_payload(qr_payload: str, food: FoodItem) -> None:
    parts = qr_payload.split("|")
    if len(parts) != 3:
        raise PeonyAPIException(
            code="INVALID_QR",
            message="QR payload format is invalid.",
            http_status=400,
        )

    qr_food_id, qr_restaurant_id, _timestamp = parts
    if qr_food_id != str(food.id) or qr_restaurant_id != str(food.restaurant_id):
        raise PeonyAPIException(
            code="INVALID_QR",
            message="QR payload does not match this food listing.",
            http_status=400,
        )


def _serialize_claim_response(claim: FoodClaim, distance_km: float) -> dict:
    food = claim.food
    restaurant = claim.restaurant
    return {
        "claim_id": str(claim.id),
        "status": claim.status,
        "food_name": f"{food.name} (1 {food.unit})",
        "restaurant_name": restaurant.name,
        "pickup_address": restaurant.address,
        "distance_km": round(distance_km, 1),
        "pickup_window": format_pickup_window(food.pickup_start, food.pickup_end),
        "claimed_at": claim.claimed_at.isoformat(),
        "message": "Show this confirmation at the counter to collect your meal.",
        "daily_limit": get_daily_limit_status(claim.receiver),
    }


def _update_food_after_claim(food: FoodItem) -> None:
    food.quantity_available -= 1
    food.quantity_claimed += 1

    if food.quantity_available <= 0:
        food.quantity_available = 0
        food.status = FoodStatus.FULLY_CLAIMED
        food.list_status = ListStatus.PAST
        food.closed_at = now_sgt()
        food.closed_reason = "FULLY_CLAIMED"
    elif food.quantity_claimed > 0:
        food.status = FoodStatus.PARTIALLY_CLAIMED

    food.save(
        update_fields=[
            "quantity_available",
            "quantity_claimed",
            "status",
            "list_status",
            "closed_at",
            "closed_reason",
            "updated_at",
        ]
    )


def _create_claim_notifications(claim: FoodClaim) -> None:
    receiver = claim.receiver
    restaurant_user = claim.restaurant.user
    food = claim.food

    Notification.objects.create(
        user=receiver,
        type="CLAIM_CONFIRMED",
        title="Meal claimed!",
        body=f"You claimed {food.name} from {claim.restaurant.name}.",
        payload={"claim_id": str(claim.id), "food_id": str(food.id)},
    )
    Notification.objects.create(
        user=restaurant_user,
        type="FOOD_CLAIMED",
        title="New claim",
        body=f"{receiver.receiver_profile.display_name} claimed {food.name}.",
        payload={"claim_id": str(claim.id), "food_id": str(food.id)},
    )


@transaction.atomic
def create_claim(
    receiver: User,
    food_id: str,
    qr_payload: str,
    lat: float,
    lng: float,
) -> dict:
    daily_limit = get_daily_limit_status(receiver)
    if not daily_limit["can_claim"]:
        raise PeonyAPIException(
            code="DAILY_LIMIT_REACHED",
            message=f"Daily limit reached ({daily_limit['limit']} per day)",
            details={"resets_at": daily_limit["resets_at"]},
            http_status=429,
        )

    try:
        food = FoodItem.objects.select_for_update().select_related("restaurant").get(id=food_id)
    except FoodItem.DoesNotExist as exc:
        raise PeonyAPIException(
            code="FOOD_UNAVAILABLE",
            message="This food listing is not available.",
            http_status=410,
        ) from exc

    now = now_sgt()
    if (
        food.list_status != ListStatus.ACTIVE
        or food.quantity_available <= 0
        or food.pickup_end <= now
    ):
        raise PeonyAPIException(
            code="FOOD_UNAVAILABLE",
            message="This food listing is no longer available.",
            http_status=410,
        )

    _validate_qr_payload(qr_payload, food)

    distance_m = haversine_distance_m(
        lat,
        lng,
        float(food.restaurant.latitude),
        float(food.restaurant.longitude),
    )
    if distance_m > settings.MAX_CLAIM_DISTANCE_M:
        raise PeonyAPIException(
            code="TOO_FAR_FROM_RESTAURANT",
            message=(
                f"You must be within {settings.MAX_CLAIM_DISTANCE_M}m of the restaurant to claim."
            ),
            details={"distance_m": round(distance_m)},
            http_status=403,
        )

    # Re-check daily limit inside transaction.
    if (
        FoodClaim.objects.filter(
            receiver=receiver,
            claim_date=today_sgt(),
            status=ClaimStatus.CLAIMED,
        ).count()
        >= settings.DAILY_CLAIM_LIMIT
    ):
        raise PeonyAPIException(
            code="DAILY_LIMIT_REACHED",
            message=f"Daily limit reached ({settings.DAILY_CLAIM_LIMIT} per day)",
            details={"resets_at": next_midnight_sgt().isoformat()},
            http_status=429,
        )

    if food.quantity_available <= 0:
        raise PeonyAPIException(
            code="RACE_CONDITION",
            message="This was the last item and has just been claimed.",
            http_status=409,
        )

    claimed_at = now_sgt()
    claim = FoodClaim.objects.create(
        food=food,
        receiver=receiver,
        restaurant=food.restaurant,
        claim_date=today_sgt(),
        claimed_at=claimed_at,
        receiver_lat=lat,
        receiver_lng=lng,
        status=ClaimStatus.CLAIMED,
        quantity_claimed=1,
    )

    _update_food_after_claim(food)

    profile = receiver.receiver_profile
    profile.total_claims += 1
    profile.last_claim_date = today_sgt()
    profile.save(update_fields=["total_claims", "last_claim_date"])

    _create_claim_notifications(claim)

    return _serialize_claim_response(claim, distance_m / 1000)


def get_claim_detail(receiver: User, claim_id: str) -> dict:
    try:
        claim = FoodClaim.objects.select_related("food", "restaurant").get(
            id=claim_id,
            receiver=receiver,
        )
    except FoodClaim.DoesNotExist as exc:
        raise PeonyAPIException(
            code="CLAIM_NOT_FOUND",
            message="Claim not found.",
            http_status=404,
        ) from exc

    distance_km = (
        haversine_distance_m(
            float(claim.receiver_lat),
            float(claim.receiver_lng),
            float(claim.restaurant.latitude),
            float(claim.restaurant.longitude),
        )
        / 1000
    )
    data = _serialize_claim_response(claim, distance_km)
    data["food"] = {
        "id": str(claim.food.id),
        "name": claim.food.name,
        "photo_url": claim.food.photo_url,
    }
    return data


def list_claim_history(receiver: User) -> dict:
    claims = (
        FoodClaim.objects.filter(receiver=receiver)
        .select_related("food", "restaurant")
        .order_by("-claimed_at")
    )

    items = []
    grouped: dict[str, list] = defaultdict(list)

    for claim in claims:
        item = {
            "id": str(claim.id),
            "food_name": claim.food.name,
            "restaurant_name": claim.restaurant.name,
            "status": claim.status,
            "claimed_at": claim.claimed_at.isoformat(),
            "pickup_window": format_pickup_window(claim.food.pickup_start, claim.food.pickup_end),
        }
        items.append(item)

        week_start = (claim.claimed_at - timedelta(days=claim.claimed_at.weekday())).date()
        grouped[week_start.isoformat()].append(item)

    grouped_by_week = [
        {"week_start": week, "claims": week_claims}
        for week, week_claims in sorted(grouped.items(), reverse=True)
    ]

    return {
        "count": len(items),
        "results": items,
        "grouped_by_week": grouped_by_week,
    }


def get_receiver_stats(receiver: User) -> dict:
    lifetime_meals = FoodClaim.objects.filter(
        receiver=receiver,
        status=ClaimStatus.CLAIMED,
    ).count()
    restaurants_count = (
        FoodClaim.objects.filter(receiver=receiver, status=ClaimStatus.CLAIMED)
        .values("restaurant_id")
        .distinct()
        .count()
    )
    return {
        "lifetime_meals": lifetime_meals,
        "restaurants_count": restaurants_count,
    }
