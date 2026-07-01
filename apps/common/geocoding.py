import re

from apps.common.exceptions import PeonyAPIException


def extract_postal_code(address: str) -> str:
    match = re.search(r"\b(\d{6})\b", address)
    return match.group(1) if match else ""


def geocode_address(address: str) -> tuple[float, float]:
    """P1 stub — integrate OneMap geocoding in production."""
    postal_code = extract_postal_code(address)
    if not postal_code:
        raise PeonyAPIException(
            code="INVALID_ADDRESS",
            message="Address must include a valid Singapore postal code.",
            http_status=400,
        )
    return 1.3521000, 103.8198000


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
