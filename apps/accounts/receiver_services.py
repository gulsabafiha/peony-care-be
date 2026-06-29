from __future__ import annotations

from django.conf import settings

from apps.accounts.models import ReceiverProfile, User
from apps.claims.services import get_receiver_stats
from apps.common.exceptions import PeonyAPIException
from apps.common.timezone_utils import SGT, now_sgt
from apps.common.uploads import delete_stored_photo, save_receiver_profile_photo


def resolve_browse_context(
    user: User,
    lat: float | None = None,
    lng: float | None = None,
    radius_km: float | None = None,
) -> tuple[float, float, float]:
    try:
        profile = user.receiver_profile
    except ReceiverProfile.DoesNotExist as exc:
        raise PeonyAPIException(
            code="PROFILE_NOT_FOUND",
            message="Receiver profile not found.",
            http_status=404,
        ) from exc

    if lat is None and lng is None:
        if profile.latitude is None or profile.longitude is None:
            raise PeonyAPIException(
                code="LOCATION_REQUIRED",
                message="Location is required. Provide lat and lng, or update your profile location.",
                http_status=400,
            )
        lat = float(profile.latitude)
        lng = float(profile.longitude)
    elif lat is None or lng is None:
        raise PeonyAPIException(
            code="INVALID_LOCATION",
            message="lat and lng must be provided together.",
            http_status=400,
        )

    if radius_km is None:
        radius_km = profile.browse_radius_km or settings.DEFAULT_BROWSE_RADIUS_KM

    return lat, lng, radius_km


def _absolute_photo_url(request, photo_url: str | None) -> str | None:
    if not photo_url:
        return None
    if photo_url.startswith("http://") or photo_url.startswith("https://"):
        return photo_url
    if request is None:
        return photo_url
    return request.build_absolute_uri(photo_url)


def get_receiver_profile(user: User, request=None) -> dict:
    try:
        profile = user.receiver_profile
    except ReceiverProfile.DoesNotExist as exc:
        raise PeonyAPIException(
            code="PROFILE_NOT_FOUND",
            message="Receiver profile not found.",
            http_status=404,
        ) from exc

    stats = get_receiver_stats(user)
    member_since = profile.created_at.astimezone(SGT).strftime("%b %Y")
    return {
        "id": str(profile.id),
        "display_name": profile.display_name,
        "phone": user.phone_e164,
        "photo_url": _absolute_photo_url(request, profile.photo_url or None),
        "latitude": float(profile.latitude) if profile.latitude is not None else None,
        "longitude": float(profile.longitude) if profile.longitude is not None else None,
        "browse_radius_km": profile.browse_radius_km,
        "member_since": member_since,
        "total_claims": profile.total_claims,
        "last_claim_date": profile.last_claim_date.isoformat() if profile.last_claim_date else None,
        "stats": stats,
    }


def update_receiver_profile(user: User, data: dict, request=None) -> dict:
    try:
        profile = user.receiver_profile
    except ReceiverProfile.DoesNotExist as exc:
        raise PeonyAPIException(
            code="PROFILE_NOT_FOUND",
            message="Receiver profile not found.",
            http_status=404,
        ) from exc

    update_fields: list[str] = []
    if "display_name" in data:
        profile.display_name = data["display_name"]
        update_fields.append("display_name")
    if "latitude" in data:
        profile.latitude = data["latitude"]
        update_fields.append("latitude")
    if "longitude" in data:
        profile.longitude = data["longitude"]
        update_fields.append("longitude")
    if "browse_radius_km" in data:
        profile.browse_radius_km = data["browse_radius_km"]
        update_fields.append("browse_radius_km")

    if data.get("remove_photo"):
        if profile.photo_url:
            delete_stored_photo(profile.photo_url)
        profile.photo_url = ""
        update_fields.append("photo_url")
    elif data.get("photo") is not None:
        if profile.photo_url:
            delete_stored_photo(profile.photo_url)
        profile.photo_url = save_receiver_profile_photo(str(user.id), data["photo"])
        update_fields.append("photo_url")

    if update_fields:
        profile.save(update_fields=update_fields)
    return get_receiver_profile(user, request=request)
