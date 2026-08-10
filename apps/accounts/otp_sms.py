"""OTP delivery providers (console / AWS SNS / Twilio Verify)."""

from __future__ import annotations

import logging

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings

from apps.common.exceptions import PeonyAPIException

logger = logging.getLogger(__name__)


def dispatch_otp(phone_e164: str, purpose: str, code: str) -> None:
    provider = (settings.OTP_PROVIDER or "console").strip().lower()
    # Always emit to stdout so `docker compose logs -f web` shows OTP activity.
    print(f"[Peony OTP] provider={provider} phone={phone_e164} purpose={purpose}", flush=True)

    if provider == "console":
        print(f"[Peony OTP] code={code} (console — SMS not sent)", flush=True)
        logger.info("OTP for %s (%s): %s", phone_e164, purpose, code)
        return

    if provider == "sns":
        _send_via_sns(phone_e164, purpose, code)
        return

    if provider == "twilio":
        # Send our generated 4-digit code via Verify custom_code.
        _send_via_twilio_verify(phone_e164, purpose, code)
        return

    raise PeonyAPIException(
        code="OTP_PROVIDER_UNAVAILABLE",
        message=f"Unknown OTP provider: {provider}",
        http_status=503,
    )


def check_twilio_verify_otp(phone_e164: str, code: str) -> bool:
    """Return True if Twilio Verify approves the code for this phone."""
    client = _twilio_client()
    service_sid = (getattr(settings, "TWILIO_VERIFY_SERVICE_SID", "") or "").strip()
    if not service_sid:
        raise PeonyAPIException(
            code="OTP_PROVIDER_UNAVAILABLE",
            message="Twilio Verify is not configured (missing TWILIO_VERIFY_SERVICE_SID).",
            http_status=503,
        )

    try:
        result = client.verify.v2.services(service_sid).verification_checks.create(
            to=phone_e164,
            code=code.strip(),
        )
    except Exception as exc:
        logger.exception("Twilio Verify check failed for %s", phone_e164)
        status = getattr(exc, "status", None)
        if status in (404, 400):
            return False
        raise PeonyAPIException(
            code="OTP_DELIVERY_FAILED",
            message="Unable to verify OTP. Please try again shortly.",
            details={"provider": "twilio"},
            http_status=502,
        ) from exc

    approved = (getattr(result, "status", "") or "").lower() == "approved"
    print(
        f"[Peony OTP] Twilio Verify check phone={phone_e164} status={result.status}",
        flush=True,
    )
    return approved


def uses_twilio_verify() -> bool:
    return (settings.OTP_PROVIDER or "console").strip().lower() == "twilio"


def _twilio_client():
    account_sid = (getattr(settings, "TWILIO_ACCOUNT_SID", "") or "").strip()
    auth_token = (getattr(settings, "TWILIO_AUTH_TOKEN", "") or "").strip()
    if not account_sid or not auth_token:
        raise PeonyAPIException(
            code="OTP_PROVIDER_UNAVAILABLE",
            message="Twilio is not configured (missing account SID or auth token).",
            http_status=503,
        )
    try:
        from twilio.rest import Client
    except ImportError as exc:
        raise PeonyAPIException(
            code="OTP_PROVIDER_UNAVAILABLE",
            message="Twilio SDK is not installed.",
            http_status=503,
        ) from exc
    return Client(account_sid, auth_token)


def _send_via_twilio_verify(phone_e164: str, purpose: str, code: str) -> None:
    client = _twilio_client()
    service_sid = (getattr(settings, "TWILIO_VERIFY_SERVICE_SID", "") or "").strip()
    if not service_sid:
        raise PeonyAPIException(
            code="OTP_PROVIDER_UNAVAILABLE",
            message="Twilio Verify is not configured (missing TWILIO_VERIFY_SERVICE_SID).",
            http_status=503,
        )

    code_length = int(getattr(settings, "TWILIO_VERIFY_CODE_LENGTH", 4) or 4)
    if code_length < 4 or code_length > 10:
        code_length = 4

    # Pad/truncate so we always send exactly code_length digits.
    custom_code = "".join(ch for ch in str(code) if ch.isdigit())
    if len(custom_code) < code_length:
        custom_code = custom_code.zfill(code_length)
    custom_code = custom_code[-code_length:]

    try:
        # Align service setting (does not always apply to in-flight SMS alone).
        service = client.verify.v2.services(service_sid).update(code_length=code_length)
        actual_length = getattr(service, "code_length", None)
        print(
            f"[Peony OTP] Twilio Verify service code_length={actual_length}",
            flush=True,
        )

        # Force the SMS body to use our 4-digit code (requires Custom Code enabled).
        # Twilio Console → Verify → Services → your service → General →
        # "Enable Custom Verification Code".
        verification = client.verify.v2.services(service_sid).verifications.create(
            to=phone_e164,
            channel="sms",
            custom_code=custom_code,
        )
    except Exception as exc:
        logger.exception("Twilio Verify send failed for %s", phone_e164)
        message = str(exc)
        if "custom" in message.lower() or getattr(exc, "status", None) == 403:
            raise PeonyAPIException(
                code="OTP_PROVIDER_UNAVAILABLE",
                message=(
                    "Twilio Custom Verification Code is not enabled. "
                    "In Twilio Console open Verify → Services → your service → "
                    "General → enable Custom Verification Code, then retry."
                ),
                details={"provider": "twilio"},
                http_status=503,
            ) from exc
        raise PeonyAPIException(
            code="OTP_DELIVERY_FAILED",
            message="Unable to send OTP SMS. Please try again shortly.",
            details={"provider": "twilio"},
            http_status=502,
        ) from exc

    sid = getattr(verification, "sid", "") or ""
    status = getattr(verification, "status", "") or ""
    print(
        f"[Peony OTP] Twilio Verify sent phone={phone_e164} purpose={purpose} "
        f"sid={sid} status={status} code_length={code_length}",
        flush=True,
    )
    logger.info(
        "OTP SMS sent via Twilio Verify to %s (purpose=%s, sid=%s, status=%s, code_length=%s)",
        phone_e164,
        purpose,
        sid,
        status,
        code_length,
    )


def _send_via_sns(phone_e164: str, purpose: str, code: str) -> None:
    region = settings.AWS_S3_REGION_NAME or "ap-southeast-1"
    message = (
        f"Your UduFood code is {code}. "
        f"It expires in {settings.OTP_EXPIRY_MINUTES} minute(s)."
    )

    client_kwargs: dict = {"region_name": region}
    if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
        client_kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
        client_kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY

    message_attributes = {
        "AWS.SNS.SMS.SMSType": {
            "DataType": "String",
            "StringValue": "Transactional",
        }
    }
    sender_id = (getattr(settings, "OTP_SMS_SENDER_ID", "") or "").strip()
    if sender_id:
        message_attributes["AWS.SNS.SMS.SenderID"] = {
            "DataType": "String",
            "StringValue": sender_id,
        }

    try:
        client = boto3.client("sns", **client_kwargs)
        response = client.publish(
            PhoneNumber=phone_e164,
            Message=message,
            MessageAttributes=message_attributes,
        )
    except (ClientError, BotoCoreError) as exc:
        logger.exception("SNS OTP publish failed for %s", phone_e164)
        raise PeonyAPIException(
            code="OTP_DELIVERY_FAILED",
            message="Unable to send OTP SMS. Please try again shortly.",
            details={"provider": "sns"},
            http_status=502,
        ) from exc

    message_id = response.get("MessageId", "")
    print(
        f"[Peony OTP] SNS sent phone={phone_e164} purpose={purpose} message_id={message_id}",
        flush=True,
    )
    logger.info(
        "OTP SMS sent via SNS to %s (purpose=%s, message_id=%s)",
        phone_e164,
        purpose,
        message_id,
    )
