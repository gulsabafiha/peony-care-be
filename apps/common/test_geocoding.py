import pytest

from apps.common.exceptions import PeonyAPIException
from apps.common.geocoding import (
    BD_GEOCODE_STUB,
    SG_GEOCODE_STUB,
    extract_postal_code,
    geocode_address,
    resolve_restaurant_coordinates,
)


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        ("443 Joo Chiat Rd, Singapore 427656", "427656"),
        ("House 12, Road 5, Dhanmondi, Dhaka 1205", "1205"),
        ("Banani, Dhaka-1213, Bangladesh", "1213"),
        ("no postal here", ""),
    ],
)
def test_extract_postal_code(address, expected):
    assert extract_postal_code(address) == expected


def test_geocode_address_from_singapore_postal_code():
    lat, lng = geocode_address("443 Joo Chiat Rd, Singapore 427656")
    assert (lat, lng) == SG_GEOCODE_STUB


def test_geocode_address_from_bangladesh_postal_code():
    lat, lng = geocode_address("House 12, Road 5, Dhanmondi, Dhaka 1205")
    assert (lat, lng) == BD_GEOCODE_STUB


def test_geocode_address_rejects_missing_postal():
    with pytest.raises(PeonyAPIException) as exc_info:
        geocode_address("Somewhere without a postal code")
    assert exc_info.value.code == "INVALID_ADDRESS"


def test_resolve_restaurant_coordinates_uses_map_pin():
    lat, lng = resolve_restaurant_coordinates(
        "443 Joo Chiat Rd, Singapore 427656",
        latitude=1.3012,
        longitude=103.8588,
    )
    assert lat == 1.3012
    assert lng == 103.8588


def test_resolve_restaurant_coordinates_geocodes_when_no_pin():
    lat, lng = resolve_restaurant_coordinates("443 Joo Chiat Rd, Singapore 427656")
    assert (lat, lng) == SG_GEOCODE_STUB


def test_resolve_restaurant_coordinates_rejects_partial_pin():
    with pytest.raises(PeonyAPIException) as exc_info:
        resolve_restaurant_coordinates(
            "443 Joo Chiat Rd, Singapore 427656",
            latitude=1.3012,
        )
    assert exc_info.value.code == "INVALID_LOCATION"
