from __future__ import annotations

from django.db import transaction
from django.db.models import Count, Q

from apps.accounts.models import User
from apps.claims.models import FoodClaim
from apps.common.choices import BOARD_CLAIM_STATUSES, ClaimStatus
from apps.common.exceptions import PeonyAPIException
from apps.common.timezone_utils import (
    format_clock_time,
    format_pickup_window,
    format_pickup_window_short,
    now_in,
    timezone_for_restaurant,
    today_in,
)
from apps.donations.models import FoodItem
from apps.donations.restaurant_services import get_restaurant_profile

STATUS_FILTER_MAP = {
    "all": None,
    "pending": ClaimStatus.CLAIMED,
    "collected": ClaimStatus.COLLECTED,
    "no_show": ClaimStatus.NO_SHOW,
}


def _initials(name: str) -> str:
    parts = [part for part in name.strip().split() if part]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0][:2].upper()
    return "".join(part[0].upper() for part in parts[:2])


def _claim_status_key(status: str) -> str:
    if status == ClaimStatus.COLLECTED:
        return "collected"
    if status == ClaimStatus.NO_SHOW:
        return "no_show"
    return "pending"


def _claim_status_label(status: str) -> str:
    if status == ClaimStatus.COLLECTED:
        return "Collected"
    if status == ClaimStatus.NO_SHOW:
        return "No-show"
    return "Pending"


def _items_label(claim: FoodClaim) -> str:
    qty = claim.quantity_claimed or 1
    return f"{qty} × {claim.food.name}"


def _serialize_restaurant_claim(claim: FoodClaim) -> dict:
    status = claim.status
    receiver_name = claim.receiver.receiver_profile.display_name
    tz = timezone_for_restaurant(claim.food.restaurant)
    collected_label = None
    if claim.collected_at:
        collected_label = f"Collected {format_clock_time(claim.collected_at, tz=tz)}"

    window_expired_label = None
    if status == ClaimStatus.NO_SHOW:
        window_expired_label = "Expired at end of day"

    return {
        "id": str(claim.id),
        "receiver_name": receiver_name,
        "receiver_initials": _initials(receiver_name),
        "food_id": str(claim.food_id),
        "food_name": claim.food.name,
        "items_label": _items_label(claim),
        "quantity_claimed": claim.quantity_claimed,
        "claimed_at": claim.claimed_at.isoformat(),
        "collected_at": claim.collected_at.isoformat() if claim.collected_at else None,
        "collected_at_label": collected_label,
        "no_show_at": claim.no_show_at.isoformat() if claim.no_show_at else None,
        "window_expired_label": window_expired_label,
        "pickup_window": format_pickup_window(
            claim.food.pickup_start,
            claim.food.pickup_end,
            tz=tz,
        ),
        "pickup_window_short": format_pickup_window_short(
            claim.food.pickup_start,
            claim.food.pickup_end,
            tz=tz,
        ),
        "status": status,
        "status_key": _claim_status_key(status),
        "status_label": _claim_status_label(status),
        "can_mark_collected": status == ClaimStatus.CLAIMED,
        "can_mark_no_show": status == ClaimStatus.CLAIMED,
        "can_undo_no_show": status == ClaimStatus.NO_SHOW,
        "actions": {
            "can_mark_collected": status == ClaimStatus.CLAIMED,
            "can_mark_no_show": status == ClaimStatus.CLAIMED,
            "can_undo_no_show": status == ClaimStatus.NO_SHOW,
        },
    }


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
        .select_related("receiver__receiver_profile", "food")
        .order_by("-claimed_at")
    )
    serialized = [_serialize_restaurant_claim(claim) for claim in claims]
    return {
        "food_id": str(food.id),
        "food_name": food.name,
        "total": len(serialized),
        "claims": serialized,
    }


def get_today_claims(user: User, status: str = "all") -> dict:
    restaurant = get_restaurant_profile(user)
    status_key = (status or "all").lower()
    if status_key not in STATUS_FILTER_MAP:
        raise PeonyAPIException(
            code="INVALID_STATUS",
            message="Status must be all, pending, collected, or no_show.",
            http_status=400,
        )

    today = today_in(timezone_for_restaurant(restaurant))
    base = FoodClaim.objects.filter(
        restaurant=restaurant,
        claim_date=today,
        status__in=BOARD_CLAIM_STATUSES,
    )
    counts = base.aggregate(
        pending=Count("id", filter=Q(status=ClaimStatus.CLAIMED)),
        collected=Count("id", filter=Q(status=ClaimStatus.COLLECTED)),
        no_show=Count("id", filter=Q(status=ClaimStatus.NO_SHOW)),
        total=Count("id"),
    )
    pending = counts["pending"] or 0
    collected = counts["collected"] or 0
    no_show = counts["no_show"] or 0
    total = counts["total"] or 0

    queryset = base.select_related("receiver__receiver_profile", "food")
    filter_status = STATUS_FILTER_MAP[status_key]
    if filter_status:
        queryset = queryset.filter(status=filter_status)

    claims = list(queryset.order_by("-claimed_at"))
    serialized = [_serialize_restaurant_claim(claim) for claim in claims]

    groups = []
    if status_key == "all":
        for key, label, claim_status in (
            ("pending", "Pending", ClaimStatus.CLAIMED),
            ("collected", "Collected", ClaimStatus.COLLECTED),
            ("no_show", "No-show", ClaimStatus.NO_SHOW),
        ):
            group_claims = [c for c in serialized if c["status"] == claim_status]
            if group_claims:
                groups.append({"key": key, "label": label, "claims": group_claims})
    elif serialized:
        groups.append(
            {
                "key": status_key,
                "label": _claim_status_label(filter_status),
                "claims": serialized,
            }
        )

    return {
        "total": total,
        "summary": {
            "pending": pending,
            "collected": collected,
            "no_show": no_show,
            "label": f"{pending} pending · {collected} collected · {no_show} no-show",
        },
        "tabs": [
            {"key": "all", "label": "All", "count": total},
            {"key": "pending", "label": "Pending", "count": pending},
            {"key": "collected", "label": "Collected", "count": collected},
            {"key": "no_show", "label": "No-show", "count": no_show},
        ],
        "selected_status": status_key,
        "groups": groups,
        "claims": serialized,
        "hint": (
            "Tap Mark collected to show a QR. Scan from the receiver app to confirm "
            "pickup. If that won't help, the status stays pending."
        ),
    }


def _get_restaurant_claim_for_update(user: User, claim_id: str) -> FoodClaim:
    restaurant = get_restaurant_profile(user)
    try:
        return (
            FoodClaim.objects.select_for_update(of=("self",))
            .select_related("receiver__receiver_profile", "food")
            .get(id=claim_id, restaurant=restaurant)
        )
    except FoodClaim.DoesNotExist as exc:
        raise PeonyAPIException(
            code="CLAIM_NOT_FOUND",                
            message="Claim not found.",
            http_status=404,
        ) from exc


@transaction.atomic
def mark_claim_collected(user: User, claim_id: str) -> dict:
    claim = _get_restaurant_claim_for_update(user, claim_id)

    if claim.status == ClaimStatus.COLLECTED:
        raise PeonyAPIException(
            code="CLAIM_ALREADY_COLLECTED",
            message="This claim is already marked as collected.",
            http_status=409,
        )

    if claim.status != ClaimStatus.CLAIMED:
        raise PeonyAPIException(
            code="CLAIM_NOT_COLLECTABLE",
            message="Only pending claims can be marked as collected.",
            http_status=409,
        )

    claim.status = ClaimStatus.COLLECTED
    claim.collected_at = now_in(timezone_for_restaurant(claim.restaurant))
    claim.no_show_at = None
    claim.save(update_fields=["status", "collected_at", "no_show_at"])
    return _serialize_restaurant_claim(claim)


@transaction.atomic
def mark_claim_no_show(user: User, claim_id: str) -> dict:
    claim = _get_restaurant_claim_for_update(user, claim_id)

    if claim.status == ClaimStatus.NO_SHOW:
        raise PeonyAPIException(
            code="CLAIM_ALREADY_NO_SHOW",
            message="This claim is already marked as no-show.",
            http_status=409,
        )

    if claim.status != ClaimStatus.CLAIMED:
        raise PeonyAPIException(
            code="CLAIM_NOT_MARKABLE",
            message="Only pending claims can be marked as no-show.",
            http_status=409,
        )

    claim.status = ClaimStatus.NO_SHOW
    claim.no_show_at = now_in(timezone_for_restaurant(claim.restaurant))
    claim.collected_at = None
    claim.save(update_fields=["status", "no_show_at", "collected_at"])
    return _serialize_restaurant_claim(claim)


@transaction.atomic
def undo_claim_no_show(user: User, claim_id: str) -> dict:
    claim = _get_restaurant_claim_for_update(user, claim_id)

    if claim.status != ClaimStatus.NO_SHOW:
        raise PeonyAPIException(
            code="CLAIM_NOT_NO_SHOW",
            message="Only no-show claims can be undone.",
            http_status=409,
        )

    claim.status = ClaimStatus.CLAIMED
    claim.no_show_at = None
    claim.save(update_fields=["status", "no_show_at"])
    return _serialize_restaurant_claim(claim)
