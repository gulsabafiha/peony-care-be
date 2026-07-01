import hashlib
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken as JWTRefreshToken

from apps.accounts.models import (
    DonorProfile,
    OtpChallenge,
    ReceiverProfile,
    RefreshToken,
    RestaurantProfile,
    User,
)
from apps.common.choices import OtpPurpose, UserRole
from apps.common.exceptions import PeonyAPIException
from apps.common.geocoding import extract_postal_code, resolve_restaurant_coordinates
from apps.common.phone import normalize_phone_e164

logger = logging.getLogger(__name__)

REGISTRATION_TOKEN_SALT = "peony.registration"


def find_user_by_phone(phone: str) -> User | None:
    phone_e164 = normalize_phone_e164(phone)
    user = User.objects.filter(phone_e164=phone_e164).first()
    if user is not None:
        return user

    for candidate in User.objects.exclude(phone_e164=phone_e164).only(
        "id", "phone_e164", "role", "is_active"
    ):
        try:
            if normalize_phone_e164(candidate.phone_e164) != phone_e164:
                continue
        except PeonyAPIException:
            continue

        if candidate.phone_e164 != phone_e164:
            candidate.phone_e164 = phone_e164
            candidate.save(update_fields=["phone_e164"])
        return candidate

    return None


def _hash_value(value: str) -> str:
    payload = f"{value}:{settings.SECRET_KEY}"
    return hashlib.sha256(payload.encode()).hexdigest()


def _generate_otp_code() -> str:
    return f"{secrets.randbelow(10_000):04d}"


def send_otp(phone: str, purpose: str) -> dict:
    phone_e164 = normalize_phone_e164(phone)

    if purpose == OtpPurpose.LOGIN:
        if not (
            (user := find_user_by_phone(phone_e164)) and user.is_active
        ):
            raise PeonyAPIException(
                code="USER_NOT_FOUND",
                message="No active account found for this phone number.",
                http_status=404,
            )

    if purpose == OtpPurpose.REGISTER:
        user = find_user_by_phone(phone_e164)
        if user and user.is_active and _user_has_any_profile(user):
            raise PeonyAPIException(
                code="ALREADY_REGISTERED",
                message="This phone number is already registered. Please log in.",
                http_status=409,
            )

    latest = OtpChallenge.objects.filter(phone_e164=phone_e164).order_by("-created_at").first()
    if latest:
        elapsed = (timezone.now() - latest.created_at).total_seconds()
        if elapsed < settings.OTP_RESEND_COOLDOWN_SECONDS:
            retry_after = int(settings.OTP_RESEND_COOLDOWN_SECONDS - elapsed)
            raise PeonyAPIException(
                code="OTP_RATE_LIMITED",
                message="Please wait before requesting another OTP.",
                details={"retry_after_seconds": retry_after},
                http_status=429,
            )

    code = _generate_otp_code()
    challenge = OtpChallenge.objects.create(
        phone_e164=phone_e164,
        code_hash=_hash_value(code),
        purpose=purpose,
        expires_at=timezone.now() + timedelta(minutes=settings.OTP_EXPIRY_MINUTES),
    )

    if settings.OTP_PROVIDER == "console":
        # Visible in `docker compose logs -f web` during development.
        print(f"[Peony OTP] {phone_e164} ({purpose}): {code}", flush=True)
        logger.info("OTP for %s (%s): %s", phone_e164, purpose, code)
    else:
        # SMS provider integration (Twilio / AWS SNS) goes here.
        logger.info("OTP dispatched via %s for %s", settings.OTP_PROVIDER, phone_e164)

    return {
        "phone": phone_e164,
        "purpose": purpose,
        "expires_at": challenge.expires_at.isoformat(),
        "message": "OTP sent successfully.",
    }


def verify_otp(phone: str, code: str) -> dict:
    phone_e164 = normalize_phone_e164(phone)
    challenge = (
        OtpChallenge.objects.filter(
            phone_e164=phone_e164,
            consumed_at__isnull=True,
            expires_at__gt=timezone.now(),
        )
        .order_by("-created_at")
        .first()
    )

    if challenge is None:
        raise PeonyAPIException(
            code="OTP_EXPIRED",
            message="OTP is invalid or has expired.",
            http_status=400,
        )

    if challenge.attempts >= settings.OTP_MAX_ATTEMPTS:
        raise PeonyAPIException(
            code="OTP_MAX_ATTEMPTS",
            message="Maximum OTP attempts exceeded. Request a new code.",
            http_status=429,
        )

    if _hash_value(code) != challenge.code_hash:
        challenge.attempts += 1
        challenge.save(update_fields=["attempts"])
        raise PeonyAPIException(
            code="INVALID_OTP",
            message="Incorrect OTP code.",
            details={"attempts_remaining": settings.OTP_MAX_ATTEMPTS - challenge.attempts},
            http_status=400,
        )

    challenge.consumed_at = timezone.now()
    challenge.save(update_fields=["consumed_at"])

    if challenge.purpose == OtpPurpose.LOGIN:
        user = find_user_by_phone(phone_e164)
        if user is None or not user.is_active:
            raise PeonyAPIException(
                code="USER_NOT_FOUND",
                message="No active account found for this phone number.",
                http_status=404,
            )
        return _issue_jwt_response(user)

    return {
        "registration_token": _create_registration_token(phone_e164),
        "phone": phone_e164,
        "message": "Phone verified. Complete registration to continue.",
    }


def _user_has_any_profile(user: User) -> bool:
    return (
        ReceiverProfile.objects.filter(user=user).exists()
        or RestaurantProfile.objects.filter(user=user).exists()
        or DonorProfile.objects.filter(user=user).exists()
    )


def _create_registration_token(phone_e164: str) -> str:
    signer = signing.TimestampSigner(salt=REGISTRATION_TOKEN_SALT)
    return signer.sign(phone_e164)


def verify_registration_token(token: str) -> str:
    signer = signing.TimestampSigner(salt=REGISTRATION_TOKEN_SALT)
    try:
        return signer.unsign(token, max_age=settings.REGISTRATION_TOKEN_MAX_AGE_SECONDS)
    except signing.BadSignature as exc:
        raise PeonyAPIException(
            code="INVALID_REGISTRATION_TOKEN",
            message="Registration token is invalid or expired.",
            http_status=401,
        ) from exc


def _issue_jwt_response(user: User) -> dict:
    refresh = JWTRefreshToken.for_user(user)
    refresh_token = str(refresh)
    access_token = str(refresh.access_token)

    RefreshToken.objects.create(
        user=user,
        token_hash=_hash_value(refresh_token),
        expires_at=timezone.now() + settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"],
    )

    return {
        "access": access_token,
        "refresh": refresh_token,
        "user": _serialize_user(user),
    }


def _serialize_user(user: User) -> dict:
    return {
        "id": str(user.id),
        "phone": user.phone_e164,
        "role": user.role,
        "is_active": user.is_active,
    }


@transaction.atomic
def register_receiver(
    phone_e164: str,
    display_name: str,
    latitude: float,
    longitude: float,
) -> dict:
    user = _get_or_create_user(phone_e164, UserRole.RECEIVER)
    if ReceiverProfile.objects.filter(user=user).exists():
        raise PeonyAPIException(
            code="ALREADY_REGISTERED",
            message="Receiver profile already exists for this phone number.",
            http_status=409,
        )

    ReceiverProfile.objects.create(
        user=user,
        display_name=display_name,
        latitude=latitude,
        longitude=longitude,
    )
    user.is_active = True
    user.save(update_fields=["is_active"])
    return _issue_jwt_response(user)


@transaction.atomic
def register_restaurant(phone_e164: str, data: dict) -> dict:
    user = _get_or_create_user(phone_e164, UserRole.RESTAURANT)
    if RestaurantProfile.objects.filter(user=user).exists():
        raise PeonyAPIException(
            code="ALREADY_REGISTERED",
            message="Restaurant profile already exists for this phone number.",
            http_status=409,
        )

    latitude, longitude = resolve_restaurant_coordinates(
        data["address"],
        data.get("latitude"),
        data.get("longitude"),
    )
    postal_code = extract_postal_code(data["address"])

    RestaurantProfile.objects.create(
        user=user,
        name=data["restaurant_name"],
        uen=data["uen"],
        address=data["address"],
        postal_code=postal_code,
        latitude=latitude,
        longitude=longitude,
        contact_name=data["contact_name"],
        contact_email=data.get("contact_email", ""),
        contact_phone=_normalize_optional_phone(data.get("contact_phone")) or phone_e164,
        is_approved=True,
        approved_at=timezone.now(),
    )
    user.is_active = True
    user.save(update_fields=["is_active"])
    return _issue_jwt_response(user)


@transaction.atomic
def register_donor(phone_e164: str, display_name: str, contact_email: str = "") -> dict:
    user = _get_or_create_user(phone_e164, UserRole.DONOR)
    if DonorProfile.objects.filter(user=user).exists():
        raise PeonyAPIException(
            code="ALREADY_REGISTERED",
            message="Donor profile already exists for this phone number.",
            http_status=409,
        )

    DonorProfile.objects.create(
        user=user,
        display_name=display_name,
        contact_email=contact_email,
    )
    user.is_active = True
    user.save(update_fields=["is_active"])
    return _issue_jwt_response(user)


def _normalize_optional_phone(phone: str | None) -> str:
    if not phone or not str(phone).strip():
        return ""
    return normalize_phone_e164(phone)


def _get_or_create_user(phone_e164: str, role: str) -> User:
    phone_e164 = normalize_phone_e164(phone_e164)
    user = find_user_by_phone(phone_e164)
    if user:
        if user.role != role:
            raise PeonyAPIException(
                code="ROLE_MISMATCH",
                message="This phone number is registered with a different role.",
                http_status=409,
            )
        return user

    return User.objects.create_user(phone_e164=phone_e164, role=role, is_active=False)


def refresh_access_token(refresh_token: str) -> dict:
    try:
        token = JWTRefreshToken(refresh_token)
    except Exception as exc:
        raise PeonyAPIException(
            code="INVALID_REFRESH_TOKEN",
            message="Refresh token is invalid or expired.",
            http_status=401,
        ) from exc

    user = User.objects.filter(id=token["user_id"], is_active=True).first()
    if user is None:
        raise PeonyAPIException(
            code="USER_NOT_FOUND",
            message="User account is not active.",
            http_status=401,
        )

    new_refresh = JWTRefreshToken.for_user(user)
    new_refresh_token = str(new_refresh)

    RefreshToken.objects.create(
        user=user,
        token_hash=_hash_value(new_refresh_token),
        expires_at=timezone.now() + settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"],
    )

    return {
        "access": str(new_refresh.access_token),
        "refresh": new_refresh_token,
    }


def logout(refresh_token: str) -> dict:
    token_hash = _hash_value(refresh_token)

    try:
        token = JWTRefreshToken(refresh_token)
        token.blacklist()
    except Exception as exc:
        raise PeonyAPIException(
            code="INVALID_REFRESH_TOKEN",
            message="Refresh token is invalid or already revoked.",
            http_status=400,
        ) from exc

    RefreshToken.objects.filter(token_hash=token_hash, revoked_at__isnull=True).update(
        revoked_at=timezone.now()
    )

    return {"message": "Logged out successfully."}
