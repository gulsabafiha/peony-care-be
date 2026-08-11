from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.db.models import Avg, Count

from apps.accounts.models import RestaurantProfile, User
from apps.claims.models import FoodClaim, RestaurantReview, ReviewTagOption
from apps.common.choices import ClaimStatus
from apps.common.exceptions import PeonyAPIException
from apps.common.timezone_utils import SGT, today_in, timezone_for_restaurant

REVIEW_TAGS = [
    ("friendly-staff", "Friendly staff", 1),
    ("fresh-tasty", "Fresh & tasty", 2),
    ("quick-pickup", "Quick pickup", 3),
    ("generous-portion", "Generous portion", 4),
    ("clean-packaging", "Clean packaging", 5),
]

RATING_LABELS = {
    1: "Poor",
    2: "Fair",
    3: "Good",
    4: "Very good",
    5: "Excellent",
}


def ensure_review_tags() -> None:
    for code, label, sort_order in REVIEW_TAGS:
        ReviewTagOption.objects.get_or_create(
            code=code,
            defaults={"label": label, "sort_order": sort_order, "is_active": True},
        )


def list_review_tags() -> list[dict]:
    ensure_review_tags()
    return [
        {"id": str(option.id), "code": option.code, "label": option.label}
        for option in ReviewTagOption.objects.filter(is_active=True)
    ]


def rating_label(rating: int | None) -> str | None:
    if rating is None:
        return None
    return RATING_LABELS.get(rating)


def restaurant_rating_stats(restaurant_id) -> dict:
    stats = RestaurantReview.objects.filter(restaurant_id=restaurant_id).aggregate(
        avg=Avg("rating"),
        count=Count("id"),
    )
    count = stats["count"] or 0
    avg = stats["avg"]
    rating = round(float(avg), 1) if avg is not None else None
    return {
        "rating": rating,
        "rating_display": "—" if rating is None else f"{rating:.1f}",
        "review_count": count,
        "reviews_label": (
            "reviews coming soon" if count == 0 else f"{count} review{'s' if count != 1 else ''}"
        ),
        "reviews_available": count > 0,
    }


def _collected_label(collected_at, *, tz=SGT) -> str:
    if not collected_at:
        return "collected"
    day = collected_at.astimezone(tz).date()
    today = today_in(tz)
    if day == today:
        return "collected today"
    if day == today - timedelta(days=1):
        return "collected yesterday"
    return f"collected {day.strftime('%b')} {day.day}"


def _serialize_tag(option: ReviewTagOption) -> dict:
    return {"id": str(option.id), "code": option.code, "label": option.label}


def _reviewer_name(review: RestaurantReview) -> str:
    profile = getattr(review.receiver, "receiver_profile", None)
    if profile and profile.display_name:
        return profile.display_name
    return ""


def _serialize_review(review: RestaurantReview) -> dict:
    tags = list(review.tags.all())
    return {
        "id": str(review.id),
        "restaurant_id": str(review.restaurant_id),
        "reviewer_name": _reviewer_name(review),
        "rating": review.rating,
        "rating_label": rating_label(review.rating),
        "tag_codes": [tag.code for tag in tags],
        "tags": [_serialize_tag(tag) for tag in tags],
        "comment": review.comment,
        "created_at": review.created_at.isoformat(),
        "updated_at": review.updated_at.isoformat(),
    }


def _load_review(review_id) -> RestaurantReview:
    return (
        RestaurantReview.objects.select_related("receiver__receiver_profile")
        .prefetch_related("tags")
        .get(id=review_id)
    )


def _get_restaurant(restaurant_id: str) -> RestaurantProfile:
    try:
        return RestaurantProfile.objects.get(id=restaurant_id)
    except RestaurantProfile.DoesNotExist as exc:
        raise PeonyAPIException(
            code="RESTAURANT_NOT_FOUND",
            message="Restaurant not found.",
            http_status=404,
        ) from exc


def _latest_collected_claim(receiver: User, restaurant: RestaurantProfile) -> FoodClaim | None:
    return (
        FoodClaim.objects.filter(
            receiver=receiver,
            restaurant=restaurant,
            status=ClaimStatus.COLLECTED,
        )
        .select_related("food")
        .order_by("-collected_at", "-claimed_at")
        .first()
    )


def _require_can_review(receiver: User, restaurant: RestaurantProfile) -> FoodClaim:
    claim = _latest_collected_claim(receiver, restaurant)
    if claim is None:
        raise PeonyAPIException(
            code="NO_COLLECTED_CLAIM",
            message="You can only review a restaurant after collecting food there.",
            http_status=400,
        )
    return claim


def _get_review(receiver: User, restaurant: RestaurantProfile) -> RestaurantReview | None:
    return (
        RestaurantReview.objects.select_related("receiver__receiver_profile")
        .prefetch_related("tags")
        .filter(receiver=receiver, restaurant=restaurant)
        .first()
    )


def _resolve_tags(
    *,
    tag_ids: list | None = None,
    tag_codes: list | None = None,
) -> list[ReviewTagOption]:
    ensure_review_tags()
    tag_ids = tag_ids or []
    tag_codes = tag_codes or []

    if not tag_ids and not tag_codes:
        return []

    if tag_ids:
        tags = list(ReviewTagOption.objects.filter(id__in=tag_ids, is_active=True))
        if len(tags) != len(set(str(tid) for tid in tag_ids)):
            raise PeonyAPIException(
                code="INVALID_REVIEW_TAG",
                message="One or more review tags are invalid.",
                http_status=400,
            )
        return tags

    tags = list(ReviewTagOption.objects.filter(code__in=tag_codes, is_active=True))
    if len(tags) != len(set(tag_codes)):
        raise PeonyAPIException(
            code="INVALID_REVIEW_TAG",
            message="One or more review tags are invalid.",
            http_status=400,
        )
    return tags


def get_review_form(receiver: User, restaurant_id: str) -> dict:
    restaurant = _get_restaurant(restaurant_id)
    latest_claim = _require_can_review(receiver, restaurant)
    review = _get_review(receiver, restaurant)
    collected = _collected_label(
        latest_claim.collected_at,
        tz=timezone_for_restaurant(restaurant),
    )
    food_name = latest_claim.food.name
    return {
        "restaurant_id": str(restaurant.id),
        "restaurant_name": restaurant.name,
        "latest_food_name": food_name,
        "collected_at": (
            latest_claim.collected_at.isoformat() if latest_claim.collected_at else None
        ),
        "collected_label": collected,
        "context_subtitle": f"{food_name} · {collected}",
        "can_review": True,
        "has_review": review is not None,
        "tags": list_review_tags(),
        "review": _serialize_review(review) if review else None,
    }


@transaction.atomic
def create_review(
    receiver: User,
    restaurant_id: str,
    *,
    rating: int,
    comment: str = "",
    tag_ids: list | None = None,
    tag_codes: list | None = None,
) -> dict:
    restaurant = _get_restaurant(restaurant_id)
    _require_can_review(receiver, restaurant)

    if _get_review(receiver, restaurant) is not None:
        raise PeonyAPIException(
            code="REVIEW_ALREADY_EXISTS",
            message="You have already reviewed this restaurant. Update or delete it instead.",
            http_status=409,
        )

    tags = _resolve_tags(tag_ids=tag_ids, tag_codes=tag_codes)
    review = RestaurantReview.objects.create(
        receiver=receiver,
        restaurant=restaurant,
        rating=rating,
        comment=(comment or "").strip(),
    )
    if tags:
        review.tags.set(tags)

    review = _load_review(review.id)
    data = _serialize_review(review)
    data["message"] = "Review submitted. Thank you!"
    data["success_message"] = "Review submitted"
    return data


@transaction.atomic
def update_review(
    receiver: User,
    restaurant_id: str,
    *,
    rating: int | None = None,
    comment: str | None = None,
    tag_ids: list | None = None,
    tag_codes: list | None = None,
) -> dict:
    restaurant = _get_restaurant(restaurant_id)
    review = _get_review(receiver, restaurant)
    if review is None:
        raise PeonyAPIException(
            code="REVIEW_NOT_FOUND",
            message="No review found for this restaurant.",
            http_status=404,
        )

    update_fields: list[str] = []
    if rating is not None:
        review.rating = rating
        update_fields.append("rating")
    if comment is not None:
        review.comment = comment.strip()
        update_fields.append("comment")
    if update_fields:
        review.save(update_fields=[*update_fields, "updated_at"])

    if tag_ids is not None or tag_codes is not None:
        tags = _resolve_tags(tag_ids=tag_ids, tag_codes=tag_codes)
        review.tags.set(tags)

    review = _load_review(review.id)
    data = _serialize_review(review)
    data["message"] = "Review updated."
    data["success_message"] = "Review updated"
    return data


@transaction.atomic
def delete_review(receiver: User, restaurant_id: str) -> dict:
    restaurant = _get_restaurant(restaurant_id)
    review = _get_review(receiver, restaurant)
    if review is None:
        raise PeonyAPIException(
            code="REVIEW_NOT_FOUND",
            message="No review found for this restaurant.",
            http_status=404,
        )
    review_id = str(review.id)
    review.delete()
    return {
        "id": review_id,
        "restaurant_id": str(restaurant.id),
        "deleted": True,
        "message": "Review deleted.",
    }
