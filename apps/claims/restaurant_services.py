from __future__ import annotations

from apps.accounts.models import User
from apps.claims.models import FoodClaim
from apps.common.choices import ClaimStatus
from apps.common.exceptions import PeonyAPIException
from apps.common.timezone_utils import format_pickup_window, today_sgt
from apps.donations.models import FoodItem
from apps.donations.restaurant_services import get_restaurant_profile


def list_donation_claims(user: User, food_id: str) -> dict:
    restaurant = get_restaurant_profile(user)
    try:
        food = FoodItem.objects.get(id=food_id, restaurant=restaurant)
    except FoodItem.DoesNotExist as exc:
        raise PeonyAPIException(
            code="DONATION_NOT_FOUND",
            message="Donation not found.",
            http_status=404,
        ) from exc

    claims = (
        FoodClaim.objects.filter(food=food)
        .select_related("receiver__receiver_profile")
        .order_by("-claimed_at")
    )
    return {
        "food_id": str(food.id),
        "food_name": food.name,
        "total": claims.count(),
        "claims": [
            {
                "id": str(claim.id),
                "receiver_name": claim.receiver.receiver_profile.display_name,
                "food_name": food.name,
                "claimed_at": claim.claimed_at.isoformat(),
                "pickup_window": format_pickup_window(food.pickup_start, food.pickup_end),
                "status": claim.status,
            }
            for claim in claims
        ],
    }


def get_today_claims(user: User) -> dict:
    restaurant = get_restaurant_profile(user)
    claims = (
        FoodClaim.objects.filter(
            restaurant=restaurant,
            claim_date=today_sgt(),
            status=ClaimStatus.CLAIMED,
        )
        .select_related("receiver__receiver_profile", "food")
        .order_by("-claimed_at")
    )

    return {
        "total": claims.count(),
        "claims": [
            {
                "id": str(claim.id),
                "receiver_name": claim.receiver.receiver_profile.display_name,
                "food_name": claim.food.name,
                "claimed_at": claim.claimed_at.isoformat(),
                "pickup_window": format_pickup_window(
                    claim.food.pickup_start,
                    claim.food.pickup_end,
                ),
                "status": claim.status,
            }
            for claim in claims
        ],
    }
