"""OTP delivery providers (console / AWS SNS)."""

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
        raise PeonyAPIException(
            code="OTP_PROVIDER_UNAVAILABLE",
            message="Twilio OTP delivery is not configured yet. Use console or sns.",
            http_status=503,
        )

    raise PeonyAPIException(
        code="OTP_PROVIDER_UNAVAILABLE",
        message=f"Unknown OTP provider: {provider}",
        http_status=503,
    )


def _send_via_sns(phone_e164: str, purpose: str, code: str) -> None:
    region = settings.AWS_S3_REGION_NAME or "ap-southeast-1"
    message = (
        f"Your MakanMenu code is {code}. "
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
