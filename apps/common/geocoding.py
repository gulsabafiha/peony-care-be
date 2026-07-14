import re

from apps.common.exceptions import PeonyAPIException

# Prefer Singapore 6-digit codes, then Bangladesh 4-digit codes.
_SG_POSTAL = re.compile(r"\b(\d{6})\b")
_BD_POSTAL = re.compile(r"\b(\d{4})\b")

SG_GEOCODE_STUB = (1.3521000, 103.8198000)
BD_GEOCODE_STUB = (23.8103000, 90.4125000)  # Dhaka — P1 stub until real geocoding


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
    """P1 stub — integrate OneMap / BD geocoding in production."""
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
