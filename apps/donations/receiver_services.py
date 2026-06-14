from __future__ import annotations

from django.conf import settings
from django.db.models import Q

from apps.common.choices import FoodStatus, ListStatus
from apps.common.exceptions import PeonyAPIException
from apps.common.geo import haversine_distance_m
from apps.common.timezone_utils import bounding_box, format_pickup_window, now_sgt
from apps.donations.models import FoodItem


def _base_available_queryset():
    now = now_sgt()
    return (
        FoodItem.objects.select_related("restaurant")
        .filter(
            list_status=ListStatus.ACTIVE,
            quantity_available__gt=0,
            pickup_end__gt=now,
            restaurant__is_approved=True,
        )
        .exclude(status=FoodStatus.EXPIRED)
    )


def _serialize_food_item(food: FoodItem, receiver_lat: float, receiver_lng: float) -> dict:
    rest = food.restaurant
    distance_m = haversine_distance_m(
        receiver_lat,
        receiver_lng,
        float(rest.latitude),
        float(rest.longitude),
    )
    return {
        "id": str(food.id),
        "name": food.name,
        "description": food.description,
        "category": food.category,
        "unit": food.unit,
        "photo_url": food.photo_url,
        "quantity_available": food.quantity_available,
        "quantity_original": food.quantity_original,
        "quantity_claimed": food.quantity_claimed,
        "status": food.status,
        "pickup_start": food.pickup_start.isoformat(),
        "pickup_end": food.pickup_end.isoformat(),
        "pickup_window": format_pickup_window(food.pickup_start, food.pickup_end),
        "distance_km": round(distance_m / 1000, 1),
        "restaurant": {
            "id": str(rest.id),
            "name": rest.name,
            "address": rest.address,
            "latitude": float(rest.latitude),
            "longitude": float(rest.longitude),
            "is_verified": rest.is_verified,
        },
        "sponsorship_type": food.sponsorship_type,
        "sponsor_display_name": food.sponsor_display_name or None,
    }


def _filter_by_radius(queryset, lat: float, lng: float, radius_km: float):
    min_lat, max_lat, min_lng, max_lng = bounding_box(lat, lng, radius_km)
    queryset = queryset.filter(
        restaurant__latitude__gte=min_lat,
        restaurant__latitude__lte=max_lat,
        restaurant__longitude__gte=min_lng,
        restaurant__longitude__lte=max_lng,
    )

    results = []
    radius_m = radius_km * 1000
    for food in queryset:
        distance_m = haversine_distance_m(
            lat,
            lng,
            float(food.restaurant.latitude),
            float(food.restaurant.longitude),
        )
        if distance_m <= radius_m:
            results.append((distance_m, food))

    results.sort(key=lambda item: item[0])
    return [item[1] for item in results]


def browse_food(lat: float, lng: float, radius_km: float | None = None) -> list[dict]:
    radius = radius_km or settings.DEFAULT_BROWSE_RADIUS_KM
    queryset = _base_available_queryset()
    foods = _filter_by_radius(queryset, lat, lng, radius)
    return [_serialize_food_item(food, lat, lng) for food in foods]


def search_food(
    lat: float,
    lng: float,
    radius_km: float | None = None,
    query: str = "",
    category: str | None = None,
) -> list[dict]:
    radius = radius_km or settings.DEFAULT_BROWSE_RADIUS_KM
    queryset = _base_available_queryset()

    if query:
        queryset = queryset.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(restaurant__name__icontains=query)
        )
    if category:
        queryset = queryset.filter(category=category)

    foods = _filter_by_radius(queryset, lat, lng, radius)
    return [_serialize_food_item(food, lat, lng) for food in foods]


def get_food_detail(food_id: str, lat: float, lng: float) -> dict:
    try:
        food = _base_available_queryset().get(id=food_id)
    except FoodItem.DoesNotExist as exc:
        raise PeonyAPIException(
            code="FOOD_UNAVAILABLE",
            message="This food listing is not available.",
            http_status=410,
        ) from exc

    detail = _serialize_food_item(food, lat, lng)
    detail["claim_progress"] = {
        "claimed": food.quantity_claimed,
        "total": food.quantity_original,
        "remaining": food.quantity_available,
        "percent_claimed": round((food.quantity_claimed / food.quantity_original) * 100)
        if food.quantity_original
        else 0,
    }
    return detail
