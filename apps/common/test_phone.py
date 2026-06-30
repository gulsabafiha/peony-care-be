import pytest

from apps.common.exceptions import PeonyAPIException
from apps.common.phone import normalize_phone_e164

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+6591234567", "+6591234567"),
        ("+65 9123 4567", "+6591234567"),
        ("91234567", "+6591234567"),
        ("65 9123 4567", "+6591234567"),
    ],
)
def test_normalize_phone_e164(raw, expected):
    assert normalize_phone_e164(raw) == expected


def test_normalize_phone_e164_rejects_invalid():
    with pytest.raises(PeonyAPIException) as exc_info:
        normalize_phone_e164("not-a-phone")
    assert exc_info.value.code == "INVALID_PHONE"
