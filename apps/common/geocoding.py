from __future__ import annotations

import math
import re

from apps.common.exceptions import PeonyAPIException

# Prefer Singapore 6-digit codes, then Bangladesh 4-digit codes.
_SG_POSTAL = re.compile(r"\b(\d{6})\b")
_BD_POSTAL = re.compile(r"\b(\d{4})\b")

SG_GEOCODE_STUB = (1.3521000, 103.8198000)
BD_GEOCODE_STUB = (23.8103000, 90.4125000)  # Dhaka — P1 stub until real geocoding

# Curated P1 stubs for search / reverse geocode until OneMap is wired.
KNOWN_LOCATIONS: list[dict] = [
    {
        "address_line": "443 Joo Chiat Road",
        "address": "443 Joo Chiat Rd, Singapore 427656",
        "postal_code": "427656",
        "latitude": 1.30680,
        "longitude": 103.90090,
        "country": "Singapore",
    },
    {
        "address_line": "1 Raffles Place",
        "address": "1 Raffles Place, Singapore 048616",
        "postal_code": "048616",
        "latitude": 1.28410,
        "longitude": 103.85150,
        "country": "Singapore",
    },
    {
        "address_line": "Orchard Road",
        "address": "Orchard Road, Singapore 238801",
        "postal_code": "238801",
        "latitude": 1.30480,
        "longitude": 103.83180,
        "country": "Singapore",
    },
    {
        "address_line": "House 12, Road 5, Dhanmondi",
        "address": "House 12, Road 5, Dhanmondi, Dhaka 1205",
        "postal_code": "1205",
        "latitude": 23.74610,
        "longitude": 90.37420,
        "country": "Bangladesh",
    },
]


def extract_postal_code(address: str) -> str:
    text = address or ""
    sg_match = _SG_POSTAL.search(text)
    if sg_match:
        return sg_match.group(1)
    bd_match = _BD_POSTAL.search(text)
    if bd_match:
        return bd_match.group(1)
    return ""


def geocode_address(address: str) -> tuple[float, float]:
    """Resolve coordinates for an address (P1 stub / known places)."""
    query = (address or "").strip().lower()
    if not query:
        raise PeonyAPIException(
            code="INVALID_ADDRESS",
            message="Address is required.",
            http_status=400,
        )

    for place in KNOWN_LOCATIONS:
        if (
            query in place["address"].lower()
            or query in place["address_line"].lower()
            or place["postal_code"] in query
        ):
            return place["latitude"], place["longitude"]

    postal_code = extract_postal_code(address)
    if not postal_code:
        raise PeonyAPIException(
            code="INVALID_ADDRESS",
            message=(
                "Address must include a valid Singapore (6-digit) "
                "or Bangladesh (4-digit) postal code."
            ),
            http_status=400,
        )
    if len(postal_code) == 6:
        return SG_GEOCODE_STUB
    return BD_GEOCODE_STUB


def resolve_restaurant_coordinates(
    address: str,
    latitude: float | None = None,
    longitude: float | None = None,
) -> tuple[float, float]:
    """Use map-pin coordinates when provided; otherwise geocode the address."""
    if latitude is not None and longitude is not None:
        return latitude, longitude
    if latitude is not None or longitude is not None:
        raise PeonyAPIException(
            code="INVALID_LOCATION",
            message="latitude and longitude must be provided together.",
            http_status=400,
        )
    return geocode_address(address)


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 6_371_000 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _serialize_location(place: dict) -> dict:
    return {
        "address_line": place["address_line"],
        "address": place["address"],
        "postal_code": place["postal_code"],
        "latitude": place["latitude"],
        "longitude": place["longitude"],
        "country": place.get("country", ""),
        "subtitle": f"{place.get('country', 'Singapore')} {place['postal_code']}",
        "display": (
            f"{place['address_line']} · {place.get('country', 'Singapore')} "
            f"{place['postal_code']} · {place['latitude']:.5f}, {place['longitude']:.5f}"
        ),
    }


def search_locations(query: str, *, limit: int = 8) -> list[dict]:
    """Search address / postal suggestions for the map pin UI."""
    text = (query or "").strip()
    if len(text) < 2:
        raise PeonyAPIException(
            code="INVALID_QUERY",
            message="Search query must be at least 2 characters.",
            http_status=400,
        )

    needle = text.lower()
    matches = []
    for place in KNOWN_LOCATIONS:
        haystack = f"{place['address']} {place['address_line']} {place['postal_code']}".lower()
        if needle in haystack:
            matches.append(_serialize_location(place))

    if not matches and extract_postal_code(text):
        lat, lng = geocode_address(text)
        postal = extract_postal_code(text)
        country = "Singapore" if len(postal) == 6 else "Bangladesh"
        matches.append(
            _serialize_location(
                {
                    "address_line": text,
                    "address": text if postal in text else f"{text}, {country} {postal}",
                    "postal_code": postal,
                    "latitude": lat,
                    "longitude": lng,
                    "country": country,
                }
            )
        )

    return matches[:limit]


def reverse_geocode(latitude: float, longitude: float) -> dict:
    """Resolve a map pin to a human-readable selected location."""
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise PeonyAPIException(
            code="INVALID_LOCATION",
            message="latitude/longitude out of range.",
            http_status=400,
        )

    nearest = None
    nearest_distance = None
    for place in KNOWN_LOCATIONS:
        distance = _haversine_m(latitude, longitude, place["latitude"], place["longitude"])
        if nearest_distance is None or distance < nearest_distance:
            nearest = place
            nearest_distance = distance

    # Snap to a known place within ~300m; otherwise keep the pin coords.
    if nearest is not None and nearest_distance is not None and nearest_distance <= 300:
        result = _serialize_location(nearest)
        result["snapped"] = True
        result["distance_m"] = round(nearest_distance)
        return result

    postal = nearest["postal_code"] if nearest else ""
    country = nearest.get("country", "Singapore") if nearest else "Singapore"
    near_enough = bool(nearest and nearest_distance is not None and nearest_distance <= 1500)
    address_line = nearest["address_line"] if near_enough else "Pinned location"
    address = (
        nearest["address"]
        if near_enough
        else f"Pinned location, {country} {postal}".strip()
    )
    return {
        "address_line": address_line,
        "address": address,
        "postal_code": postal,
        "latitude": round(latitude, 5),
        "longitude": round(longitude, 5),
        "country": country,
        "subtitle": f"{country} {postal} · {latitude:.5f}, {longitude:.5f}".strip(),
        "display": f"{address_line} · {country} {postal} · {latitude:.5f}, {longitude:.5f}".strip(),
        "snapped": False,
        "distance_m": round(nearest_distance) if nearest_distance is not None else None,
    }
