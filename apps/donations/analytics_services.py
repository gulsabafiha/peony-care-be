from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum

from apps.accounts.models import User
from apps.claims.models import FoodClaim
from apps.common.choices import (
    COUNTED_CLAIM_STATUSES,
    CreditPreference,
    MealOrderStatus,
    SponsorshipType,
)
from apps.common.exceptions import PeonyAPIException
from apps.common.timezone_utils import (
    SGT,
    WEEKDAY_LABELS,
    now_sgt,
    start_of_week_sgt,
    today_sgt,
)
from apps.donations.models import FoodItem
from apps.donations.restaurant_services import get_restaurant_profile
from apps.donors.models import MealOrder

RANGE_OPTIONS = ("7D", "30D", "3M", "1Y", "ALL")
HEATMAP_WEEKS = 4


def _format_sgd(amount: Decimal | int | float | str) -> str:
    value = Decimal(str(amount)).quantize(Decimal("0.01"))
    if value == value.to_integral():
        return f"S${int(value)}"
    return f"S${value}"


def _initials(name: str) -> str:
    parts = [part for part in name.strip().split() if part]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0][:2].upper()
    return "".join(part[0].upper() for part in parts[:2])


def _parse_range(range_key: str) -> tuple[str, date | None, date]:
    key = (range_key or "30D").upper()
    if key not in RANGE_OPTIONS:
        raise PeonyAPIException(
            code="INVALID_RANGE",
            message="range must be one of 7D, 30D, 3M, 1Y, ALL.",
            http_status=400,
        )
    end = today_sgt() + timedelta(days=1)  # exclusive
    if key == "ALL":
        return key, None, end
    days = {"7D": 7, "30D": 30, "3M": 90, "1Y": 365}[key]
    start = end - timedelta(days=days)
    return key, start, end


def _datetime_start(day: date | None) -> datetime | None:
    if day is None:
        return None
    return datetime.combine(day, datetime.min.time(), tzinfo=SGT)


def _week_over_week_pct(this_week: int, last_week: int) -> int:
    if last_week <= 0:
        return 100 if this_week > 0 else 0
    return round(((this_week - last_week) / last_week) * 100)


def _meals_in_period(restaurant, start: date | None, end: date) -> int:
    qs = FoodClaim.objects.filter(
        restaurant=restaurant,
        status__in=COUNTED_CLAIM_STATUSES,
        claim_date__lt=end,
    )
    if start is not None:
        qs = qs.filter(claim_date__gte=start)
    return qs.aggregate(total=Sum("quantity_claimed"))["total"] or 0


def _weekly_buckets(
    restaurant,
    start: date | None,
    end: date,
    *,
    max_weeks: int = 12,
) -> list[dict]:
    """Build weekly meal + claim-rate points for charts."""
    end_week = start_of_week_sgt(end - timedelta(days=1))
    if start is None:
        first_claim = (
            FoodClaim.objects.filter(
                restaurant=restaurant,
                status__in=COUNTED_CLAIM_STATUSES,
            )
            .order_by("claim_date")
            .values_list("claim_date", flat=True)
            .first()
        )
        first_food = (
            FoodItem.objects.filter(restaurant=restaurant)
            .order_by("created_at")
            .values_list("created_at", flat=True)
            .first()
        )
        earliest = first_claim
        if first_food is not None:
            food_day = first_food.astimezone(SGT).date()
            earliest = food_day if earliest is None else min(earliest, food_day)
        week_start = start_of_week_sgt(earliest or today_sgt())
    else:
        week_start = start_of_week_sgt(start)

    # Cap number of weeks for chart readability.
    span_weeks = max(((end_week - week_start).days // 7) + 1, 1)
    if span_weeks > max_weeks:
        week_start = end_week - timedelta(days=7 * (max_weeks - 1))
        span_weeks = max_weeks

    claims = FoodClaim.objects.filter(
        restaurant=restaurant,
        status__in=COUNTED_CLAIM_STATUSES,
        claim_date__gte=week_start,
        claim_date__lt=end,
    ).values("claim_date", "quantity_claimed")

    meals_by_week: dict[str, int] = defaultdict(int)
    for row in claims:
        key = start_of_week_sgt(row["claim_date"]).isoformat()
        meals_by_week[key] += row["quantity_claimed"] or 0

    foods = FoodItem.objects.filter(
        restaurant=restaurant,
        created_at__gte=_datetime_start(week_start),
        created_at__lt=_datetime_start(end),
    ).values("created_at", "quantity_original", "quantity_claimed")

    offered_by_week: dict[str, int] = defaultdict(int)
    claimed_by_week: dict[str, int] = defaultdict(int)
    for food in foods:
        key = start_of_week_sgt(food["created_at"].astimezone(SGT).date()).isoformat()
        offered_by_week[key] += food["quantity_original"] or 0
        claimed_by_week[key] += food["quantity_claimed"] or 0

    rows = []
    for index in range(span_weeks):
        ws = week_start + timedelta(days=7 * index)
        key = ws.isoformat()
        meals = meals_by_week.get(key, 0)
        offered = offered_by_week.get(key, 0)
        claimed = claimed_by_week.get(key, 0)
        rate = round((claimed / offered) * 100) if offered else 0
        rows.append(
            {
                "week": f"W{index + 1}",
                "week_start": key,
                "week_end": (ws + timedelta(days=6)).isoformat(),
                "meals": meals,
                "claim_rate_pct": rate,
            }
        )
    return rows


def _donation_source(restaurant, start: date | None, end: date) -> dict:
    foods = FoodItem.objects.filter(restaurant=restaurant, created_at__lt=_datetime_start(end))
    if start is not None:
        foods = foods.filter(created_at__gte=_datetime_start(start))

    totals = foods.aggregate(
        total=Count("id"),
        direct=Count("id", filter=Q(sponsorship_type=SponsorshipType.DIRECT)),
        sponsored=Count(
            "id",
            filter=Q(
                sponsorship_type__in=[
                    SponsorshipType.SPONSORED_NAMED,
                    SponsorshipType.SPONSORED_ANONYMOUS,
                ]
            ),
        ),
    )
    total = totals["total"] or 0
    direct = totals["direct"] or 0
    sponsored = totals["sponsored"] or 0
    direct_pct = round((direct / total) * 100) if total else 0
    sponsored_pct = round((sponsored / total) * 100) if total else 0
    return {
        "total": total,
        "direct": {
            "count": direct,
            "pct": direct_pct,
            "label": "Direct",
            "detail": f"{direct_pct}% from your kitchen",
        },
        "sponsored": {
            "count": sponsored,
            "pct": sponsored_pct,
            "label": "Sponsored",
            "detail": f"{sponsored_pct}% paid by donors",
        },
    }


def _claim_heatmap(restaurant) -> dict:
    end = today_sgt() + timedelta(days=1)
    start = start_of_week_sgt(today_sgt()) - timedelta(days=7 * (HEATMAP_WEEKS - 1))

    claims = FoodClaim.objects.filter(
        restaurant=restaurant,
        status__in=COUNTED_CLAIM_STATUSES,
        claim_date__gte=start,
        claim_date__lt=end,
    ).values("claim_date", "quantity_claimed")

    grid: dict[str, list[int]] = {}
    for index in range(HEATMAP_WEEKS):
        ws = start + timedelta(days=7 * index)
        grid[ws.isoformat()] = [0] * 7

    max_value = 0
    for row in claims:
        ws = start_of_week_sgt(row["claim_date"])
        key = ws.isoformat()
        if key not in grid:
            continue
        day_index = row["claim_date"].weekday()  # Mon=0
        grid[key][day_index] += row["quantity_claimed"] or 0
        max_value = max(max_value, grid[key][day_index])

    weeks = []
    for index in range(HEATMAP_WEEKS):
        ws = start + timedelta(days=7 * index)
        values = grid[ws.isoformat()]
        weeks.append(
            {
                "week": f"W{index + 1}",
                "week_start": ws.isoformat(),
                "values": values,
                "days": [
                    {
                        "day": WEEKDAY_LABELS[i],
                        "date": (ws + timedelta(days=i)).isoformat(),
                        "count": values[i],
                        "intensity": (
                            0 if max_value == 0 else round((values[i] / max_value) * 4)
                        ),
                    }
                    for i in range(7)
                ],
            }
        )

    return {
        "title": "Claim activity — last 4 weeks",
        "day_labels": WEEKDAY_LABELS,
        "max_value": max_value,
        "weeks": weeks,
        "legend": {"less": 0, "more": max_value, "steps": 5},
    }


def _most_claimed_dishes(
    restaurant,
    start: date | None,
    end: date,
    *,
    limit: int = 3,
) -> list[dict]:
    foods = FoodItem.objects.filter(
        restaurant=restaurant,
        created_at__lt=_datetime_start(end),
    )
    if start is not None:
        foods = foods.filter(created_at__gte=_datetime_start(start))

    # Aggregate by dish name across listings in range.
    by_name: dict[str, dict] = {}
    for food in foods.only(
        "name",
        "photo_url",
        "quantity_original",
        "quantity_claimed",
    ):
        bucket = by_name.setdefault(
            food.name,
            {
                "name": food.name,
                "photo_url": food.photo_url or None,
                "meals": 0,
                "quantity_original": 0,
            },
        )
        bucket["meals"] += food.quantity_claimed or 0
        bucket["quantity_original"] += food.quantity_original or 0
        if not bucket["photo_url"] and food.photo_url:
            bucket["photo_url"] = food.photo_url

    dishes = []
    for item in by_name.values():
        original = item["quantity_original"]
        rate = round((item["meals"] / original) * 100) if original else 0
        dishes.append(
            {
                "name": item["name"],
                "photo_url": item["photo_url"],
                "meals": item["meals"],
                "claim_rate_pct": rate,
                "detail": f"{item['meals']} meals · {rate}% claim rate",
            }
        )
    dishes.sort(key=lambda row: (-row["meals"], row["name"]))
    return dishes[:limit]


def _sponsors(restaurant, start: date | None, end: date, *, limit: int = 5) -> list[dict]:
    orders = (
        MealOrder.objects.filter(
            restaurant=restaurant,
            status=MealOrderStatus.POSTED,
            created_at__lt=_datetime_start(end),
        )
        .select_related("donor", "food_item")
        .prefetch_related("items")
    )
    if start is not None:
        orders = orders.filter(created_at__gte=_datetime_start(start))

    named: dict[str, dict] = {}
    anonymous = {
        "key": "anonymous",
        "display_name": "Anonymous donors",
        "initials": "",
        "is_anonymous": True,
        "sponsored_count": 0,
        "amount_sgd": Decimal("0.00"),
    }

    for order in orders:
        qty = sum(item.quantity for item in order.items.all())
        amount = order.total_amount_sgd or Decimal("0.00")
        preference = order.credit_preference
        if preference == CreditPreference.ANONYMOUS or (
            order.food_item
            and order.food_item.sponsorship_type == SponsorshipType.SPONSORED_ANONYMOUS
        ):
            anonymous["sponsored_count"] += qty
            anonymous["amount_sgd"] += amount
            continue

        donor = order.donor
        key = str(donor.id)
        bucket = named.setdefault(
            key,
            {
                "key": key,
                "display_name": donor.display_name,
                "initials": _initials(donor.display_name),
                "is_anonymous": False,
                "photo_url": donor.photo_url or None,
                "sponsored_count": 0,
                "amount_sgd": Decimal("0.00"),
            },
        )
        if preference == CreditPreference.INITIALS:
            bucket["display_name"] = _initials(donor.display_name)
        bucket["sponsored_count"] += qty
        bucket["amount_sgd"] += amount

    sponsors = list(named.values())
    if anonymous["sponsored_count"] or anonymous["amount_sgd"]:
        sponsors.append(anonymous)

    sponsors.sort(
        key=lambda row: (-row["sponsored_count"], -row["amount_sgd"], row["display_name"])
    )
    result = []
    for row in sponsors[:limit]:
        amount = Decimal(row["amount_sgd"]).quantize(Decimal("0.01"))
        result.append(
            {
                "display_name": row["display_name"],
                "initials": row["initials"],
                "is_anonymous": row["is_anonymous"],
                "photo_url": row.get("photo_url"),
                "sponsored_count": row["sponsored_count"],
                "amount_sgd": str(amount),
                "amount_display": _format_sgd(amount),
                "detail": (
                    f"{row['sponsored_count']} sponsored · {_format_sgd(amount)}"
                ),
            }
        )
    return result


def get_restaurant_analytics(user: User, range_key: str = "30D") -> dict:
    restaurant = get_restaurant_profile(user)
    selected_range, start, end = _parse_range(range_key)

    all_foods = FoodItem.objects.filter(restaurant=restaurant)
    donations_all_time = all_foods.count()
    is_empty = donations_all_time == 0

    foods_in_range = all_foods.filter(created_at__lt=_datetime_start(end))
    if start is not None:
        foods_in_range = foods_in_range.filter(created_at__gte=_datetime_start(start))

    donations_posted = foods_in_range.count()
    total_original = foods_in_range.aggregate(total=Sum("quantity_original"))["total"] or 0
    people_fed = _meals_in_period(restaurant, start, end)
    claim_rate_pct = round((people_fed / total_original) * 100) if total_original else None

    week_start = start_of_week_sgt(today_sgt())
    this_week_meals = _meals_in_period(
        restaurant,
        week_start,
        week_start + timedelta(days=7),
    )
    last_week_meals = _meals_in_period(
        restaurant,
        week_start - timedelta(days=7),
        week_start,
    )
    week_over_week_pct = _week_over_week_pct(this_week_meals, last_week_meals)

    weekly = _weekly_buckets(restaurant, start, end)
    meals_total = sum(row["meals"] for row in weekly)
    latest_rate = weekly[-1]["claim_rate_pct"] if weekly else (claim_rate_pct or 0)

    sponsored_total = MealOrder.objects.filter(
        restaurant=restaurant,
        status=MealOrderStatus.POSTED,
        created_at__lt=_datetime_start(end),
    )
    if start is not None:
        sponsored_total = sponsored_total.filter(created_at__gte=_datetime_start(start))
    sponsored_amount = sponsored_total.aggregate(total=Sum("total_amount_sgd"))["total"] or Decimal(
        "0.00"
    )

    source = _donation_source(restaurant, start, end)
    heatmap = _claim_heatmap(restaurant)
    top_dishes = _most_claimed_dishes(restaurant, start, end)
    sponsors = _sponsors(restaurant, start, end)

    return {
        "is_empty": is_empty,
        "selected_range": selected_range,
        "range_options": list(RANGE_OPTIONS),
        "empty_state": {
            "title": "No analytics yet",
            "subtitle": (
                "Post your first donation to start tracking impact — lives fed, "
                "claim rate, peak hours, and repeat receivers."
            ),
            "cta_label": "+ Post a donation",
        }
        if is_empty
        else None,
        "total_impact": {
            "lives_fed": people_fed,
            "donations": donations_posted,
            "claim_rate_pct": claim_rate_pct or 0,
            "subtitle": (
                f"across {donations_posted} donations · "
                f"{claim_rate_pct if claim_rate_pct is not None else 0}% claim rate"
            ),
            "week_over_week_pct": week_over_week_pct,
            "week_over_week_label": f"{week_over_week_pct:+d}% this week",
        },
        "impact": {
            "people_fed": people_fed,
            "people_fed_label": "lifetime" if selected_range == "ALL" else selected_range.lower(),
            "donations_posted": donations_posted,
            "donations_label": "posted",
            "claim_rate_pct": claim_rate_pct,
            "claim_rate_label": (
                "no claims yet" if claim_rate_pct is None else "claim rate"
            ),
            "claim_rate_display": "—" if claim_rate_pct is None else f"{claim_rate_pct}%",
            "sponsored_sgd": str(Decimal(sponsored_amount).quantize(Decimal("0.01"))),
            "sponsored_display": _format_sgd(sponsored_amount),
            "sponsored_label": "from donors",
        },
        "meals_donated": {
            "title": "Meals donated · weekly",
            "total": meals_total,
            "weeks": [
                {
                    "week": row["week"],
                    "week_start": row["week_start"],
                    "week_end": row["week_end"],
                    "meals": row["meals"],
                }
                for row in weekly
            ],
            "has_data": any(row["meals"] for row in weekly),
            "caption": (
                None
                if any(row["meals"] for row in weekly)
                else "Chart will populate once donations start rolling in."
            ),
        },
        "claim_rate_trend": {
            "title": "Claim rate trend",
            "current_pct": latest_rate if weekly else (claim_rate_pct or 0),
            "weeks": [
                {
                    "week": row["week"],
                    "week_start": row["week_start"],
                    "week_end": row["week_end"],
                    "claim_rate_pct": row["claim_rate_pct"],
                }
                for row in weekly
            ],
            "has_data": any(row["claim_rate_pct"] for row in weekly),
        },
        "donation_source": source,
        "claim_activity_heatmap": heatmap,
        "quick_stats": {
            "donations": donations_posted,
            "meals": people_fed,
            "claim_rate_pct": claim_rate_pct or 0,
        },
        "most_claimed_dishes": top_dishes,
        "sponsors": sponsors,
        "meals_per_week": {
            # Backward-compatible alias used by empty-state clients.
            "title": "Meals per week (last 8 weeks)",
            "weeks": [
                {
                    "week": row["week"],
                    "week_start": row["week_start"],
                    "week_end": row["week_end"],
                    "meals": row["meals"],
                }
                for row in weekly
            ],
            "has_data": any(row["meals"] for row in weekly),
            "caption": (
                None
                if any(row["meals"] for row in weekly)
                else "Chart will populate once donations start rolling in."
            ),
        },
        "insights": {
            "week_over_week_pct": week_over_week_pct,
            "generated_at": now_sgt().isoformat(),
        },
    }
