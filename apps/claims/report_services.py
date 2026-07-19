from __future__ import annotations

from apps.accounts.models import User
from apps.claims.models import ClaimReport, ClaimReportReasonOption, FoodClaim
from apps.common.exceptions import PeonyAPIException
from apps.common.timezone_utils import format_pickup_window_short
from apps.donations.restaurant_services import get_restaurant_profile

CLAIM_REPORT_REASONS = [
    ("abusive-or-rude", "Receiver was abusive or rude", 1),
    ("repeated-no-shows", "Repeated no-shows", 2),
    ("fake-or-duplicate", "Suspected fake or duplicate account", 3),
    ("tried-to-resell", "Tried to resell the food", 4),
    ("other", "Something else", 5),
]


def ensure_claim_report_reasons() -> None:
    for code, label, sort_order in CLAIM_REPORT_REASONS:
        ClaimReportReasonOption.objects.get_or_create(
            code=code,
            defaults={"label": label, "sort_order": sort_order, "is_active": True},
        )


def list_claim_report_reasons() -> list[dict]:
    ensure_claim_report_reasons()
    return [
        {
            "id": str(option.id),
            "code": option.code,
            "label": option.label,
        }
        for option in ClaimReportReasonOption.objects.filter(is_active=True)
    ]


def _mask_phone_tail(phone: str) -> str:
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    if len(digits) >= 3:
        return digits[-3:]
    return "***"


def _get_restaurant_claim(user: User, claim_id: str) -> FoodClaim:
    restaurant = get_restaurant_profile(user)
    try:
        return FoodClaim.objects.select_related(
            "receiver__receiver_profile",
            "food",
            "restaurant",
        ).get(id=claim_id, restaurant=restaurant)
    except FoodClaim.DoesNotExist as exc:
        raise PeonyAPIException(
            code="CLAIM_NOT_FOUND",
            message="Claim not found.",
            http_status=404,
        ) from exc


def get_claim_report_context(user: User, claim_id: str) -> dict:
    claim = _get_restaurant_claim(user, claim_id)
    receiver = claim.receiver.receiver_profile
    phone_tail = _mask_phone_tail(claim.receiver.phone_e164)
    pickup = format_pickup_window_short(claim.food.pickup_start, claim.food.pickup_end)
    context_line = (
        f"Reporting {receiver.display_name} (mobile — {phone_tail} · "
        f"{claim.food.name}, {pickup} pickup). Your report is confidential."
    )
    return {
        "claim_id": str(claim.id),
        "receiver_name": receiver.display_name,
        "receiver_phone_tail": phone_tail,
        "food_name": claim.food.name,
        "pickup_window_short": pickup,
        "context_line": context_line,
        "footer_note": (
            "We review every report within 24 hours and may restrict accounts "
            "that breach our community rules."
        ),
        "reasons": list_claim_report_reasons(),
    }


def _serialize_claim_report(report: ClaimReport) -> dict:
    return {
        "id": str(report.id),
        "claim_id": str(report.claim_id),
        "receiver_name": report.reported_receiver.receiver_profile.display_name,
        "reason_id": str(report.reason_option_id),
        "reason_code": report.reason_option.code,
        "reason_label": report.reason_option.label,
        "comment": report.comment,
        "created_at": report.created_at.isoformat(),
        "message": "Report submitted. Our team will review it within 24 hours.",
    }


def submit_claim_report(
    user: User,
    claim_id: str,
    *,
    reason_id: str | None = None,
    reason_code: str | None = None,
    comment: str = "",
) -> dict:
    claim = _get_restaurant_claim(user, claim_id)
    ensure_claim_report_reasons()

    reason = None
    if reason_id:
        reason = ClaimReportReasonOption.objects.filter(id=reason_id, is_active=True).first()
    elif reason_code:
        reason = ClaimReportReasonOption.objects.filter(code=reason_code, is_active=True).first()

    if reason is None:
        raise PeonyAPIException(
            code="INVALID_REPORT_REASON",
            message="Report reason not found or is no longer available.",
            http_status=400,
        )

    if ClaimReport.objects.filter(
        reporter=user,
        claim=claim,
        reason_option=reason,
    ).exists():
        raise PeonyAPIException(
            code="REPORT_ALREADY_SUBMITTED",
            message="You have already submitted this report for this claim.",
            http_status=409,
        )

    report = ClaimReport.objects.create(
        reporter=user,
        claim=claim,
        restaurant=claim.restaurant,
        reported_receiver=claim.receiver,
        reason_option=reason,
        comment=comment or "",
    )
    report = ClaimReport.objects.select_related(
        "reason_option",
        "reported_receiver__receiver_profile",
    ).get(id=report.id)
    return _serialize_claim_report(report)
