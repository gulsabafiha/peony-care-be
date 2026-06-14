import math

import pytest

from apps.common.geo import haversine_distance_m


@pytest.mark.parametrize(
    ("lat1", "lng1", "lat2", "lng2", "expected_km"),
    [
        (1.3521, 103.8198, 1.3521, 103.8198, 0.0),
        (1.3521, 103.8198, 1.3530, 103.8200, 0.1),
    ],
)
def test_haversine_distance(lat1, lng1, lat2, lng2, expected_km):
    distance_m = haversine_distance_m(lat1, lng1, lat2, lng2)
    assert math.isclose(distance_m / 1000, expected_km, abs_tol=0.2)
