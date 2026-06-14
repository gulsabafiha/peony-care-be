import re

from apps.common.exceptions import PeonyAPIException


def extract_postal_code(address: str) -> str:
    match = re.search(r"\b(\d{6})\b", address)
    return match.group(1) if match else ""


def geocode_address(address: str) -> tuple[str, str]:
    """P1 stub — integrate OneMap geocoding in production."""
    postal_code = extract_postal_code(address)
    if not postal_code:
        raise PeonyAPIException(
            code="INVALID_ADDRESS",
            message="Address must include a valid Singapore postal code.",
            http_status=400,
        )
    return "1.3521000", "103.8198000"
