from __future__ import annotations

import time

from django.db import transaction
from django.db.models import Sum

from apps.accounts.models import RestaurantProfile, User
from apps.claims.models import FoodClaim
from apps.common.choices import ClaimStatus, ClosedReason, FoodStatus, ListStatus
from apps.common.exceptions import PeonyAPIException
from apps.common.geocoding import extract_postal_code, geocode_address
from apps.common.timezone_utils import format_pickup_window, now_sgt, today_sgt
from apps.donations.models import FoodItem


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


def _serialize_restaurant_donation(food: FoodItem, include_claims: bool = False) -> dict:
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
        "status": food.status,
        "list_status": food.list_status,
        "pickup_start": food.pickup_start.isoformat(),
        "pickup_end": food.pickup_end.isoformat(),
        "pickup_window": format_pickup_window(food.pickup_start, food.pickup_end),
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


def get_dashboard(user: User) -> dict:
    restaurant = get_restaurant_profile(user)
    foods = FoodItem.objects.filter(restaurant=restaurant)
    claims = FoodClaim.objects.filter(restaurant=restaurant, status=ClaimStatus.CLAIMED)

    total_original = foods.aggregate(total=Sum("quantity_original"))["total"] or 0
    total_claimed = claims.count()
    claim_rate = round((total_claimed / total_original) * 100) if total_original else 0

    year_start = now_sgt().replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    active_foods = foods.filter(list_status=ListStatus.ACTIVE, pickup_end__gt=now_sgt())

    return {
        "lives_impacted": total_claimed,
        "donations_this_year": foods.filter(created_at__gte=year_start).count(),
        "claim_rate_pct": claim_rate,
        "active_count": active_foods.count(),
        "claimed_today": claims.filter(claim_date=today_sgt()).count(),
        "today_listings": [
            _serialize_restaurant_donation(food)
            for food in active_foods.order_by("pickup_end")[:10]
        ],
    }


def list_donations(user: User, status: str = "active") -> list[dict]:
    restaurant = get_restaurant_profile(user)
    queryset = FoodItem.objects.filter(restaurant=restaurant)

    if status == "active":
        queryset = queryset.filter(list_status=ListStatus.ACTIVE)
    elif status == "past":
        queryset = queryset.filter(list_status=ListStatus.PAST)
    elif status == "inactive":
        queryset = queryset.filter(list_status=ListStatus.INACTIVE)
    else:
        raise PeonyAPIException(
            code="INVALID_STATUS",
            message="Status must be active, past, or inactive.",
            http_status=400,
        )

    return [_serialize_restaurant_donation(food) for food in queryset.order_by("-created_at")]


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
        "contact_phone",
        "opening_hours",
        "about",
        "photo_url",
    )
    for field in profile_fields:
        if field in data:
            setattr(restaurant, field, data[field])

    if "address" in data:
        restaurant.address = data["address"]
        restaurant.postal_code = extract_postal_code(data["address"])
        lat, lng = geocode_address(data["address"])
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
