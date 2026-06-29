from __future__ import annotations

import secrets
import time
from decimal import Decimal

from django.conf import settings
from django.db import transaction

from apps.accounts.models import DonorProfile, RestaurantProfile, User
from apps.claims.models import FoodClaim
from apps.common.choices import (
    ClaimStatus,
    CreditPreference,
    FoodCategory,
    FoodStatus,
    ListStatus,
    MealOrderStatus,
    MoneyDonationStatus,
    SponsorshipType,
)
from apps.common.exceptions import PeonyAPIException
from apps.common.timezone_utils import format_pickup_window, now_sgt
from apps.donations.models import FoodItem, MenuItem
from apps.donors.models import MealOrder, MealOrderItem, MoneyDonation


def get_donor_profile(user: User) -> DonorProfile:
    try:
        return user.donor_profile
    except DonorProfile.DoesNotExist as exc:
        raise PeonyAPIException(
            code="PROFILE_NOT_FOUND",
            message="Donor profile not found.",
            http_status=404,
        ) from exc


def _initials(name: str) -> str:
    parts = [part for part in name.strip().split() if part]
    if not parts:
        return "XX"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return "".join(part[0].upper() for part in parts[:2])


def _resolve_sponsor_display(
    donor: DonorProfile,
    credit_preference: str | None = None,
) -> tuple[str, str]:
    preference = credit_preference or donor.credit_preference
    if preference == CreditPreference.ANONYMOUS:
        return SponsorshipType.SPONSORED_ANONYMOUS, ""
    if preference == CreditPreference.INITIALS:
        return SponsorshipType.SPONSORED_NAMED, _initials(donor.display_name)
    return SponsorshipType.SPONSORED_NAMED, donor.display_name


def _serialize_donor_profile(donor: DonorProfile) -> dict:
    return {
        "id": str(donor.id),
        "display_name": donor.display_name,
        "contact_email": donor.contact_email,
        "photo_url": donor.photo_url or None,
        "credit_preference": donor.credit_preference,
        "total_meals_sponsored": donor.total_meals_sponsored,
        "total_amount_donated_sgd": str(donor.total_amount_donated_sgd),
        "created_at": donor.created_at.isoformat(),
    }


def get_profile_data(user: User) -> dict:
    donor = get_donor_profile(user)
    data = _serialize_donor_profile(donor)
    data["phone"] = user.phone_e164
    return data


def update_profile_data(user: User, data: dict) -> dict:
    donor = get_donor_profile(user)
    for field in ("display_name", "contact_email", "photo_url"):
        if field in data:
            setattr(donor, field, data[field])
    donor.save()
    return get_profile_data(user)


def get_credit_preference(user: User) -> dict:
    donor = get_donor_profile(user)
    return {"credit_preference": donor.credit_preference}


def update_credit_preference(user: User, credit_preference: str) -> dict:
    donor = get_donor_profile(user)
    donor.credit_preference = credit_preference
    donor.save(update_fields=["credit_preference"])
    return {"credit_preference": donor.credit_preference}


def _count_lives_impacted(donor: DonorProfile) -> int:
    return FoodClaim.objects.filter(
        food__individual_donor=donor,
        status=ClaimStatus.CLAIMED,
    ).count()


def _recent_donations(donor: DonorProfile, limit: int = 10) -> list[dict]:
    meal_entries = [
        {
            "type": "MEAL",
            "id": str(order.id),
            "restaurant_name": order.restaurant.name,
            "amount_sgd": str(order.total_amount_sgd),
            "status": order.status,
            "created_at": order.created_at.isoformat(),
        }
        for order in MealOrder.objects.filter(donor=donor)
        .select_related("restaurant")
        .order_by("-created_at")[:limit]
    ]
    money_entries = [
        {
            "type": "MONEY",
            "id": str(donation.id),
            "restaurant_name": None,
            "amount_sgd": str(donation.amount_sgd),
            "status": donation.status,
            "created_at": donation.created_at.isoformat(),
        }
        for donation in MoneyDonation.objects.filter(donor=donor).order_by("-created_at")[:limit]
    ]
    combined = meal_entries + money_entries
    combined.sort(key=lambda item: item["created_at"], reverse=True)
    return combined[:limit]


def get_dashboard(user: User) -> dict:
    donor = get_donor_profile(user)
    return {
        "total_meals_sponsored": donor.total_meals_sponsored,
        "total_amount_donated_sgd": str(donor.total_amount_donated_sgd),
        "lives_impacted": _count_lives_impacted(donor),
        "recent_donations": _recent_donations(donor),
    }


def get_history(user: User) -> list[dict]:
    donor = get_donor_profile(user)
    entries: list[dict] = []

    for order in (
        MealOrder.objects.filter(donor=donor)
        .select_related("restaurant", "food_item")
        .prefetch_related("items__menu_item")
        .order_by("-created_at")
    ):
        entries.append(
            {
                "type": "MEAL",
                "id": str(order.id),
                "restaurant_id": str(order.restaurant_id),
                "restaurant_name": order.restaurant.name,
                "amount_sgd": str(order.total_amount_sgd),
                "status": order.status,
                "food_item_id": str(order.food_item_id) if order.food_item_id else None,
                "items": [
                    {
                        "menu_item_name": item.menu_item.name,
                        "quantity": item.quantity,
                        "unit_price_sgd": str(item.unit_price_sgd),
                    }
                    for item in order.items.all()
                ],
                "created_at": order.created_at.isoformat(),
            }
        )

    for donation in MoneyDonation.objects.filter(donor=donor).order_by("-created_at"):
        entries.append(
            {
                "type": "MONEY",
                "id": str(donation.id),
                "amount_sgd": str(donation.amount_sgd),
                "reference_code": donation.reference_code,
                "is_anonymous": donation.is_anonymous,
                "status": donation.status,
                "transfer_marked_at": (
                    donation.transfer_marked_at.isoformat() if donation.transfer_marked_at else None
                ),
                "confirmed_at": (
                    donation.confirmed_at.isoformat() if donation.confirmed_at else None
                ),
                "created_at": donation.created_at.isoformat(),
            }
        )

    entries.sort(key=lambda item: item["created_at"], reverse=True)
    return entries


def get_impact(user: User) -> dict:
    donor = get_donor_profile(user)
    monthly: dict[str, dict] = {}

    meal_orders = (
        MealOrder.objects.filter(donor=donor, status=MealOrderStatus.POSTED)
        .prefetch_related("items")
        .order_by("created_at")
    )
    for order in meal_orders:
        month = order.created_at.astimezone(now_sgt().tzinfo).strftime("%Y-%m")
        bucket = monthly.setdefault(month, {"month": month, "meals": 0, "amount_sgd": "0.00"})
        bucket["meals"] += sum(item.quantity for item in order.items.all())

    money_donations = MoneyDonation.objects.filter(
        donor=donor,
        status=MoneyDonationStatus.CONFIRMED,
    ).order_by("created_at")
    for donation in money_donations:
        month = donation.created_at.astimezone(now_sgt().tzinfo).strftime("%Y-%m")
        bucket = monthly.setdefault(month, {"month": month, "meals": 0, "amount_sgd": "0.00"})
        current = Decimal(bucket["amount_sgd"])
        bucket["amount_sgd"] = str(current + donation.amount_sgd)

    return {
        "total_meals_sponsored": donor.total_meals_sponsored,
        "total_amount_donated_sgd": str(donor.total_amount_donated_sgd),
        "lives_impacted": _count_lives_impacted(donor),
        "monthly": sorted(monthly.values(), key=lambda item: item["month"]),
    }


def _serialize_restaurant_browse(restaurant: RestaurantProfile) -> dict:
    return {
        "id": str(restaurant.id),
        "name": restaurant.name,
        "address": restaurant.address,
        "postal_code": restaurant.postal_code,
        "latitude": float(restaurant.latitude),
        "longitude": float(restaurant.longitude),
        "photo_url": restaurant.photo_url or None,
        "is_verified": restaurant.is_verified,
        "menu_item_count": restaurant.menu_items.filter(is_available=True).count(),
    }


def list_restaurants() -> list[dict]:
    restaurants = RestaurantProfile.objects.order_by("name")
    return [_serialize_restaurant_browse(restaurant) for restaurant in restaurants]


def get_restaurant_menu(restaurant_id: str) -> dict:
    try:
        restaurant = RestaurantProfile.objects.get(id=restaurant_id)
    except RestaurantProfile.DoesNotExist as exc:
        raise PeonyAPIException(
            code="RESTAURANT_NOT_FOUND",
            message="Restaurant not found.",
            http_status=404,
        ) from exc

    menu_items = [
        {
            "id": str(item.id),
            "name": item.name,
            "description": item.description,
            "price_sgd": str(item.price_sgd),
            "photo_url": item.photo_url or None,
            "is_available": item.is_available,
            "sort_order": item.sort_order,
        }
        for item in restaurant.menu_items.filter(is_available=True).order_by("sort_order", "name")
    ]
    return {
        "restaurant_id": str(restaurant.id),
        "restaurant_name": restaurant.name,
        "menu_items": menu_items,
    }


def _generate_qr_data(food: FoodItem) -> str:
    return f"{food.id}|{food.restaurant_id}|{int(time.time())}"


def _generate_reference_code(donor: DonorProfile) -> str:
    year = now_sgt().year
    for _ in range(10):
        suffix = secrets.token_hex(2).upper()
        code = f"PNY-{_initials(donor.display_name)}-{year}{suffix}"
        if not MoneyDonation.objects.filter(reference_code=code).exists():
            return code
    raise PeonyAPIException(
        code="REFERENCE_CODE_FAILED",
        message="Could not generate a unique reference code.",
        http_status=500,
    )


def _build_food_name(order_items: list[MealOrderItem]) -> str:
    if len(order_items) == 1:
        item = order_items[0]
        return f"{item.menu_item.name} x{item.quantity}"
    names = [f"{item.menu_item.name} x{item.quantity}" for item in order_items]
    return "Sponsored: " + ", ".join(names)


@transaction.atomic
def create_meal_order(user: User, data: dict) -> dict:
    donor = get_donor_profile(user)
    try:
        restaurant = RestaurantProfile.objects.get(id=data["restaurant_id"])
    except RestaurantProfile.DoesNotExist as exc:
        raise PeonyAPIException(
            code="RESTAURANT_NOT_FOUND",
            message="Restaurant not found.",
            http_status=404,
        ) from exc

    if data["pickup_end"] <= now_sgt():
        raise PeonyAPIException(
            code="INVALID_PICKUP_WINDOW",
            message="Pickup end must be in the future.",
            http_status=400,
        )

    menu_item_ids = [item["menu_item_id"] for item in data["items"]]
    menu_items = {
        str(item.id): item
        for item in MenuItem.objects.filter(
            id__in=menu_item_ids,
            restaurant=restaurant,
            is_available=True,
        )
    }
    if len(menu_items) != len(set(menu_item_ids)):
        raise PeonyAPIException(
            code="INVALID_MENU_ITEMS",
            message="One or more menu items are invalid or unavailable.",
            http_status=400,
        )

    credit_preference = data.get("credit_preference", donor.credit_preference)
    sponsorship_type, sponsor_display_name = _resolve_sponsor_display(
        donor,
        credit_preference,
    )

    total_amount = Decimal("0.00")
    order = MealOrder.objects.create(
        donor=donor,
        restaurant=restaurant,
        total_amount_sgd=Decimal("0.00"),
        credit_preference=credit_preference,
        status=MealOrderStatus.PENDING,
    )

    order_items: list[MealOrderItem] = []
    total_quantity = 0
    for item_data in data["items"]:
        menu_item = menu_items[str(item_data["menu_item_id"])]
        line_total = menu_item.price_sgd * item_data["quantity"]
        total_amount += line_total
        total_quantity += item_data["quantity"]
        order_items.append(
            MealOrderItem.objects.create(
                meal_order=order,
                menu_item=menu_item,
                quantity=item_data["quantity"],
                unit_price_sgd=menu_item.price_sgd,
            )
        )

    order.total_amount_sgd = total_amount
    order.save(update_fields=["total_amount_sgd"])

    primary_item = order_items[0].menu_item
    food = FoodItem.objects.create(
        restaurant=restaurant,
        name=_build_food_name(order_items),
        description=primary_item.description,
        category=FoodCategory.OTHER,
        unit="pack",
        photo_url=primary_item.photo_url,
        quantity_original=total_quantity,
        quantity_available=total_quantity,
        quantity_claimed=0,
        status=FoodStatus.AVAILABLE,
        list_status=ListStatus.ACTIVE,
        pickup_start=data["pickup_start"],
        pickup_end=data["pickup_end"],
        sponsorship_type=sponsorship_type,
        individual_donor=donor,
        sponsor_display_name=sponsor_display_name,
        meal_order_id=order.id,
    )
    food.food_qr_data = _generate_qr_data(food)
    food.save(update_fields=["food_qr_data", "updated_at"])

    order.food_item = food
    order.status = MealOrderStatus.POSTED
    order.save(update_fields=["food_item", "status"])

    restaurant.total_food_shared += total_quantity
    restaurant.save(update_fields=["total_food_shared"])

    donor.total_meals_sponsored += total_quantity
    donor.save(update_fields=["total_meals_sponsored"])

    return {
        "id": str(order.id),
        "restaurant_id": str(restaurant.id),
        "restaurant_name": restaurant.name,
        "total_amount_sgd": str(order.total_amount_sgd),
        "credit_preference": order.credit_preference,
        "status": order.status,
        "food_item": {
            "id": str(food.id),
            "name": food.name,
            "quantity_available": food.quantity_available,
            "pickup_window": format_pickup_window(food.pickup_start, food.pickup_end),
            "food_qr_data": food.food_qr_data,
            "sponsor_display_name": food.sponsor_display_name or None,
            "sponsorship_type": food.sponsorship_type,
        },
        "items": [
            {
                "menu_item_id": str(item.menu_item_id),
                "menu_item_name": item.menu_item.name,
                "quantity": item.quantity,
                "unit_price_sgd": str(item.unit_price_sgd),
            }
            for item in order_items
        ],
        "created_at": order.created_at.isoformat(),
    }


@transaction.atomic
def create_money_donation(user: User, data: dict) -> dict:
    donor = get_donor_profile(user)
    is_anonymous = data.get("is_anonymous", False)
    reference_code = _generate_reference_code(donor)

    donation = MoneyDonation.objects.create(
        donor=donor,
        amount_sgd=data["amount_sgd"],
        reference_code=reference_code,
        is_anonymous=is_anonymous,
        status=MoneyDonationStatus.PENDING_TRANSFER,
    )

    return {
        "id": str(donation.id),
        "amount_sgd": str(donation.amount_sgd),
        "reference_code": donation.reference_code,
        "is_anonymous": donation.is_anonymous,
        "status": donation.status,
        "paynow": {
            "uen": settings.PAYNOW_UEN,
            "account_name": settings.PAYNOW_ACCOUNT_NAME,
            "reference_code": donation.reference_code,
        },
        "created_at": donation.created_at.isoformat(),
    }


@transaction.atomic
def confirm_money_transfer(user: User, donation_id: str) -> dict:
    donor = get_donor_profile(user)
    try:
        donation = MoneyDonation.objects.select_for_update().get(
            id=donation_id,
            donor=donor,
        )
    except MoneyDonation.DoesNotExist as exc:
        raise PeonyAPIException(
            code="DONATION_NOT_FOUND",
            message="Money donation not found.",
            http_status=404,
        ) from exc

    if donation.status != MoneyDonationStatus.PENDING_TRANSFER:
        raise PeonyAPIException(
            code="INVALID_DONATION_STATUS",
            message="Only pending transfers can be marked as sent.",
            http_status=409,
        )

    if donation.transfer_marked_at:
        raise PeonyAPIException(
            code="TRANSFER_ALREADY_MARKED",
            message="Transfer has already been marked as sent.",
            http_status=409,
        )

    donation.transfer_marked_at = now_sgt()
    donation.save(update_fields=["transfer_marked_at"])

    return {
        "id": str(donation.id),
        "amount_sgd": str(donation.amount_sgd),
        "reference_code": donation.reference_code,
        "status": donation.status,
        "transfer_marked_at": donation.transfer_marked_at.isoformat(),
    }
