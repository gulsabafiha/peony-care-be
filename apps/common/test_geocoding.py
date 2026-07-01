import pytest

from apps.common.exceptions import PeonyAPIException
from apps.common.geocoding import geocode_address, resolve_restaurant_coordinates

pytestmark = pytest.mark.django_db


def test_geocode_address_from_postal_code():
    lat, lng = geocode_address("443 Joo Chiat Rd, Singapore 427656")
    assert lat == 1.3521000
    assert lng == 103.8198000


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
    assert lat == 1.3521000
    assert lng == 103.8198000


def test_resolve_restaurant_coordinates_rejects_partial_pin():
    with pytest.raises(PeonyAPIException) as exc_info:
        resolve_restaurant_coordinates(
            "443 Joo Chiat Rd, Singapore 427656",
            latitude=1.3012,
        )
    assert exc_info.value.code == "INVALID_LOCATION"
