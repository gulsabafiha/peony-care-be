from __future__ import annotations

from django.conf import settings
from django.db.models import Count, Q

from apps.accounts.models import RestaurantProfile, User
from apps.common.choices import FoodCategory, FoodStatus, ListStatus
from apps.common.exceptions import PeonyAPIException
from apps.common.geo import haversine_distance_m
from apps.common.timezone_utils import bounding_box, format_pickup_window, now_sgt
from apps.donations.models import FoodItem, FoodReport, FoodReportReasonOption


def _base_available_queryset():
    now = now_sgt()
    return (
        FoodItem.objects.select_related("restaurant")
        .filter(
            list_status=ListStatus.ACTIVE,
            quantity_available__gt=0,
            pickup_end__gt=now,
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


def _active_meal_count_filter(now):
    return Q(
        food_items__list_status=ListStatus.ACTIVE,
        food_items__quantity_available__gt=0,
        food_items__pickup_end__gt=now,
    ) & ~Q(food_items__status=FoodStatus.EXPIRED)


def _filter_restaurants_by_radius(queryset, lat: float, lng: float, radius_km: float):
    min_lat, max_lat, min_lng, max_lng = bounding_box(lat, lng, radius_km)
    queryset = queryset.filter(
        latitude__gte=min_lat,
        latitude__lte=max_lat,
        longitude__gte=min_lng,
        longitude__lte=max_lng,
    )

    results = []
    radius_m = radius_km * 1000
    for restaurant in queryset:
        distance_m = haversine_distance_m(
            lat,
            lng,
            float(restaurant.latitude),
            float(restaurant.longitude),
        )
        if distance_m <= radius_m:
            results.append((distance_m, restaurant))

    results.sort(key=lambda item: item[0])
    return [item[1] for item in results]


def _serialize_restaurant_browse(
    restaurant: RestaurantProfile,
    receiver_lat: float,
    receiver_lng: float,
) -> dict:
    distance_m = haversine_distance_m(
        receiver_lat,
        receiver_lng,
        float(restaurant.latitude),
        float(restaurant.longitude),
    )
    return {
        "id": str(restaurant.id),
        "name": restaurant.name,
        "address": restaurant.address,
        "postal_code": restaurant.postal_code,
        "latitude": float(restaurant.latitude),
        "longitude": float(restaurant.longitude),
        "photo_url": restaurant.photo_url or None,
        "is_verified": restaurant.is_verified,
        "distance_km": round(distance_m / 1000, 1),
        "active_meal_count": restaurant.active_meal_count,
    }


def browse_restaurants(lat: float, lng: float, radius_km: float | None = None) -> list[dict]:
    radius = radius_km or settings.DEFAULT_BROWSE_RADIUS_KM
    now = now_sgt()
    queryset = RestaurantProfile.objects.annotate(
        active_meal_count=Count("food_items", filter=_active_meal_count_filter(now)),
    )
    restaurants = _filter_restaurants_by_radius(queryset, lat, lng, radius)
    return [_serialize_restaurant_browse(restaurant, lat, lng) for restaurant in restaurants]


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


def _serialize_meal_summary(food: FoodItem) -> dict:
    return {
        "id": str(food.id),
        "name": food.name,
        "description": food.description,
        "category": food.category,
        "photo_url": food.photo_url or None,
        "quantity_available": food.quantity_available,
        "pickup_start": food.pickup_start.isoformat(),
        "pickup_end": food.pickup_end.isoformat(),
        "pickup_window": format_pickup_window(food.pickup_start, food.pickup_end),
        "sponsorship_type": food.sponsorship_type,
        "sponsor_display_name": food.sponsor_display_name or None,
    }


def _meal_category_labels(foods: list[FoodItem]) -> list[str]:
    categories = sorted({food.category for food in foods})
    return [FoodCategory(category).label for category in categories]


def get_restaurant_detail(restaurant_id: str, lat: float, lng: float) -> dict:
    try:
        restaurant = RestaurantProfile.objects.select_related("user").get(id=restaurant_id)
    except RestaurantProfile.DoesNotExist as exc:
        raise PeonyAPIException(
            code="RESTAURANT_NOT_FOUND",
            message="Restaurant not found.",
            http_status=404,
        ) from exc

    foods = list(
        _base_available_queryset()
        .filter(restaurant=restaurant)
        .order_by("pickup_start", "name")
    )
    distance_m = haversine_distance_m(
        lat,
        lng,
        float(restaurant.latitude),
        float(restaurant.longitude),
    )
    contact_phone = restaurant.contact_phone or restaurant.user.phone_e164

    return {
        "id": str(restaurant.id),
        "name": restaurant.name,
        "address": restaurant.address,
        "postal_code": restaurant.postal_code,
        "latitude": float(restaurant.latitude),
        "longitude": float(restaurant.longitude),
        "photo_url": restaurant.photo_url or None,
        "about": restaurant.about,
        "opening_hours": restaurant.opening_hours,
        "contact_phone": contact_phone,
        "is_verified": restaurant.is_verified,
        "distance_km": round(distance_m / 1000, 1),
        "active_meal_count": len(foods),
        "categories": _meal_category_labels(foods),
        "available_meals": [_serialize_meal_summary(food) for food in foods],
    }


def list_food_report_reasons() -> list[dict]:
    options = FoodReportReasonOption.objects.filter(is_active=True)
    return [
        {"id": str(option.id), "code": option.code, "label": option.label}
        for option in options
    ]


def _serialize_food_report(report: FoodReport) -> dict:
    food = report.food_item
    restaurant = report.restaurant
    reason = report.reason_option
    return {
        "id": str(report.id),
        "food_id": str(food.id),
        "food_name": food.name,
        "restaurant_id": str(restaurant.id),
        "restaurant_name": restaurant.name,
        "reason_id": str(reason.id),
        "reason_code": reason.code,
        "reason_label": reason.label,
        "comment": report.comment,
        "created_at": report.created_at.isoformat(),
    }


def submit_food_report(
    reporter: User,
    food_id: str,
    reason_id: str,
    comment: str = "",
) -> dict:
    try:
        food = FoodItem.objects.select_related("restaurant").get(id=food_id)
    except FoodItem.DoesNotExist as exc:
        raise PeonyAPIException(
            code="FOOD_NOT_FOUND",
            message="Food listing not found.",
            http_status=404,
        ) from exc

    try:
        reason_option = FoodReportReasonOption.objects.get(id=reason_id, is_active=True)
    except FoodReportReasonOption.DoesNotExist as exc:
        raise PeonyAPIException(
            code="INVALID_REPORT_REASON",
            message="Report reason not found or is no longer available.",
            http_status=400,
        ) from exc

    report = FoodReport.objects.create(
        reporter=reporter,
        food_item=food,
        restaurant=food.restaurant,
        reason_option=reason_option,
        comment=comment,
    )
    return _serialize_food_report(report)
