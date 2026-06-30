import phonenumbers

from apps.common.exceptions import PeonyAPIException

PHONE_REGION = "SG"


def normalize_phone_e164(phone: str) -> str:
    if not phone or not str(phone).strip():
        raise PeonyAPIException(
            code="INVALID_PHONE",
            message="Phone number must be a valid E.164 number.",
            http_status=400,
        )

    try:
        parsed = phonenumbers.parse(str(phone).strip(), PHONE_REGION)
    except phonenumbers.NumberParseException as exc:
        raise PeonyAPIException(
            code="INVALID_PHONE",
            message="Phone number must be a valid E.164 number.",
            http_status=400,
        ) from exc

    if not phonenumbers.is_valid_number(parsed):
        raise PeonyAPIException(
            code="INVALID_PHONE",
            message="Phone number must be a valid E.164 number.",
            http_status=400,
        )

    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
