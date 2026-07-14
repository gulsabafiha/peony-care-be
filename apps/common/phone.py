import phonenumbers

from apps.common.exceptions import PeonyAPIException

# Singapore and Bangladesh — local numbers without + are tried in this order.
PHONE_REGIONS = ("SG", "BD")


def normalize_phone_e164(phone: str) -> str:
    if not phone or not str(phone).strip():
        raise PeonyAPIException(
            code="INVALID_PHONE",
            message="Phone number must be a valid E.164 number.",
            http_status=400,
        )

    raw = str(phone).strip()
    for region in PHONE_REGIONS:
        try:
            parsed = phonenumbers.parse(raw, region)
        except phonenumbers.NumberParseException:
            continue
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)

    raise PeonyAPIException(
        code="INVALID_PHONE",
        message="Phone number must be a valid E.164 number.",
        http_status=400,
    )
