"""Play Store reviewer accounts: fixed OTP, no SMS."""

from __future__ import annotations

from django.conf import settings

from apps.common.phone import normalize_phone_e164


def review_otp_code() -> str:
    return (getattr(settings, "PLAY_STORE_REVIEW_OTP", "") or "1234").strip()


def review_phone_set() -> set[str]:
    raw = getattr(settings, "PLAY_STORE_REVIEW_PHONES", "") or ""
    phones: set[str] = set()
    for part in raw.split(","):
        value = part.strip()
        if not value:
            continue
        try:
            phones.add(normalize_phone_e164(value))
        except Exception:
            continue
    return phones


def is_play_store_review_phone(phone_e164: str) -> bool:
    return phone_e164 in review_phone_set()


def is_play_store_review_otp(phone_e164: str, code: str) -> bool:
    return is_play_store_review_phone(phone_e164) and code.strip() == review_otp_code()
