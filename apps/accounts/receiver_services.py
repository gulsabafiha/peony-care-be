from __future__ import annotations

from apps.accounts.models import ReceiverProfile, User
from apps.claims.services import get_receiver_stats
from apps.common.exceptions import PeonyAPIException


def get_receiver_profile(user: User) -> dict:
    try:
        profile = user.receiver_profile
    except ReceiverProfile.DoesNotExist as exc:
        raise PeonyAPIException(
            code="PROFILE_NOT_FOUND",
            message="Receiver profile not found.",
            http_status=404,
        ) from exc

    stats = get_receiver_stats(user)
    return {
        "id": str(profile.id),
        "display_name": profile.display_name,
        "phone": user.phone_e164,
        "total_claims": profile.total_claims,
        "last_claim_date": profile.last_claim_date.isoformat() if profile.last_claim_date else None,
        "stats": stats,
    }


def update_receiver_profile(user: User, display_name: str) -> dict:
    try:
        profile = user.receiver_profile
    except ReceiverProfile.DoesNotExist as exc:
        raise PeonyAPIException(
            code="PROFILE_NOT_FOUND",
            message="Receiver profile not found.",
            http_status=404,
        ) from exc

    profile.display_name = display_name
    profile.save(update_fields=["display_name"])
    return get_receiver_profile(user)
