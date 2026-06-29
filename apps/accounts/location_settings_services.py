from __future__ import annotations

from django.conf import settings

from apps.accounts.models import ReceiverLocationHistory, ReceiverProfile, User
from apps.common.exceptions import PeonyAPIException
from apps.common.timezone_utils import now_sgt

ALLOWED_BROWSE_RADIUS_KM = [1, 2, 3, 5, 10]
MAX_LOCATION_HISTORY_ITEMS = 50


def _get_profile(user: User) -> ReceiverProfile:
    try:
        return user.receiver_profile
    except ReceiverProfile.DoesNotExist as exc:
        raise PeonyAPIException(
            code="PROFILE_NOT_FOUND",
            message="Receiver profile not found.",
            http_status=404,
        ) from exc


def _serialize_history_item(entry: ReceiverLocationHistory) -> dict:
    return {
        "id": str(entry.id),
        "place_name": entry.place_name,
        "area_label": entry.area_label,
        "place_type": entry.place_type,
        "latitude": float(entry.latitude),
        "longitude": float(entry.longitude),
        "visited_at": entry.visited_at.isoformat(),
    }


def get_location_settings(user: User) -> dict:
    profile = _get_profile(user)
    history = ReceiverLocationHistory.objects.filter(receiver=user)[:MAX_LOCATION_HISTORY_ITEMS]
    return {
        "browse_radius_km": profile.browse_radius_km,
        "radius_options_km": ALLOWED_BROWSE_RADIUS_KM,
        "location_services_enabled": profile.location_services_enabled,
        "save_location_history": profile.save_location_history,
        "latitude": float(profile.latitude) if profile.latitude is not None else None,
        "longitude": float(profile.longitude) if profile.longitude is not None else None,
        "recent_places_count": history.count(),
        "recent_places": [_serialize_history_item(entry) for entry in history],
    }


def update_location_settings(user: User, data: dict) -> dict:
    profile = _get_profile(user)
    update_fields: list[str] = []

    if "browse_radius_km" in data:
        profile.browse_radius_km = data["browse_radius_km"]
        update_fields.append("browse_radius_km")
    if "location_services_enabled" in data:
        profile.location_services_enabled = data["location_services_enabled"]
        update_fields.append("location_services_enabled")
    if "save_location_history" in data:
        profile.save_location_history = data["save_location_history"]
        update_fields.append("save_location_history")
        if not data["save_location_history"]:
            ReceiverLocationHistory.objects.filter(receiver=user).delete()
    if "latitude" in data:
        profile.latitude = data["latitude"]
        update_fields.append("latitude")
    if "longitude" in data:
        profile.longitude = data["longitude"]
        update_fields.append("longitude")

    if update_fields:
        profile.save(update_fields=update_fields)
    return get_location_settings(user)


def record_location_visit(user: User, data: dict) -> dict | None:
    profile = _get_profile(user)
    if not profile.save_location_history:
        return None

    entry = ReceiverLocationHistory.objects.create(
        receiver=user,
        place_name=data["place_name"],
        area_label=data["area_label"],
        place_type=data.get("place_type", "OTHER"),
        latitude=data["latitude"],
        longitude=data["longitude"],
        visited_at=now_sgt(),
    )

    excess_ids = (
        ReceiverLocationHistory.objects.filter(receiver=user)
        .order_by("-visited_at")
        .values_list("id", flat=True)[MAX_LOCATION_HISTORY_ITEMS:]
    )
    if excess_ids:
        ReceiverLocationHistory.objects.filter(id__in=list(excess_ids)).delete()

    return _serialize_history_item(entry)


def clear_location_history(user: User) -> dict:
    ReceiverLocationHistory.objects.filter(receiver=user).delete()
    return {"cleared": True, "recent_places_count": 0}
