from __future__ import annotations

import json
import logging
from datetime import timedelta

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

from apps.accounts.data_export_pdf import build_receiver_data_pdf
from apps.accounts.models import ReceiverDataExport, ReceiverLocationHistory, ReceiverProfile, User
from apps.claims.models import FoodClaim
from apps.claims.services import get_receiver_stats
from apps.common.exceptions import PeonyAPIException
from apps.common.timezone_utils import SGT
from apps.common.uploads import delete_stored_photo
from apps.donations.models import FoodReport
from apps.notifications.models import Notification, NotificationSettings

logger = logging.getLogger(__name__)

DELETE_CONFIRMATION_TEXT = "DELETE"
DATA_EXPORT_COOLDOWN_HOURS = 48


def _get_receiver_profile(user: User) -> ReceiverProfile:
    try:
        return user.receiver_profile
    except ReceiverProfile.DoesNotExist as exc:
        raise PeonyAPIException(
            code="PROFILE_NOT_FOUND",
            message="Receiver profile not found.",
            http_status=404,
        ) from exc


def build_receiver_data_export(user: User) -> dict:
    profile = _get_receiver_profile(user)
    claims = (
        FoodClaim.objects.filter(receiver=user)
        .select_related("food", "restaurant")
        .order_by("-claimed_at")
    )
    location_history = ReceiverLocationHistory.objects.filter(receiver=user).order_by("-visited_at")
    reports = (
        FoodReport.objects.filter(reporter=user)
        .select_related("food_item", "restaurant", "reason_option")
        .order_by("-created_at")
    )

    notification_settings = None
    settings_obj = NotificationSettings.objects.filter(user=user).first()
    if settings_obj:
        notification_settings = {
            "push_enabled": settings_obj.push_enabled,
            "email_enabled": settings_obj.email_enabled,
            "alert_new_claim": settings_obj.alert_new_claim,
            "alert_sponsored": settings_obj.alert_sponsored,
            "alert_all_claimed": settings_obj.alert_all_claimed,
            "alert_window_expiring": settings_obj.alert_window_expiring,
            "alert_donation_claimed": settings_obj.alert_donation_claimed,
            "alert_receipts": settings_obj.alert_receipts,
        }

    return {
        "exported_at": timezone.now().isoformat(),
        "profile": {
            "id": str(profile.id),
            "display_name": profile.display_name,
            "phone": user.phone_e164,
            "photo_url": profile.photo_url or None,
            "member_since": profile.created_at.astimezone(SGT).strftime("%b %Y"),
            "browse_radius_km": profile.browse_radius_km,
            "location_services_enabled": profile.location_services_enabled,
            "save_location_history": profile.save_location_history,
            "latitude": float(profile.latitude) if profile.latitude is not None else None,
            "longitude": float(profile.longitude) if profile.longitude is not None else None,
            "stats": get_receiver_stats(user),
        },
        "claims": [
            {
                "id": str(claim.id),
                "food_name": claim.food.name,
                "restaurant_name": claim.restaurant.name,
                "pickup_address": claim.restaurant.address,
                "status": claim.status,
                "claimed_at": claim.claimed_at.isoformat(),
                "claim_date": claim.claim_date.isoformat(),
            }
            for claim in claims
        ],
        "location_history": [
            {
                "place_name": entry.place_name,
                "area_label": entry.area_label,
                "place_type": entry.place_type,
                "latitude": float(entry.latitude),
                "longitude": float(entry.longitude),
                "visited_at": entry.visited_at.isoformat(),
            }
            for entry in location_history
        ],
        "notification_settings": notification_settings,
        "reports_submitted": [
            {
                "id": str(report.id),
                "food_name": report.food_item.name,
                "restaurant_name": report.restaurant.name,
                "reason": report.reason_option.label,
                "comment": report.comment,
                "created_at": report.created_at.isoformat(),
            }
            for report in reports
        ],
        "notifications": [
            {
                "type": notification.type,
                "title": notification.title,
                "body": notification.body,
                "created_at": notification.created_at.isoformat(),
                "read_at": notification.read_at.isoformat() if notification.read_at else None,
            }
            for notification in Notification.objects.filter(user=user).order_by("-created_at")
        ],
    }


def _log_data_export(user: User, download_path: str) -> None:
    download_url = default_storage.url(download_path)
    logger.info(
        "[Peony Data Export] %s (%s) | file=%s",
        user.phone_e164,
        user.id,
        download_url,
    )


def generate_data_export_pdf(user: User) -> bytes:
    _get_receiver_profile(user)
    return build_receiver_data_pdf(user)


@transaction.atomic
def request_data_export(user: User, request=None) -> dict:
    _get_receiver_profile(user)
    cutoff = timezone.now() - timedelta(hours=DATA_EXPORT_COOLDOWN_HOURS)
    if ReceiverDataExport.objects.filter(user=user, requested_at__gte=cutoff).exists():
        raise PeonyAPIException(
            code="EXPORT_ALREADY_REQUESTED",
            message="A data export was requested recently. Please try again later.",
            http_status=429,
        )

    export_record = ReceiverDataExport.objects.create(
        user=user,
        phone_e164=user.phone_e164,
        status=ReceiverDataExport.Status.PENDING,
    )

    pdf_bytes = build_receiver_data_pdf(user)
    filename = f"exports/receivers/{user.id}/{export_record.id}.pdf"
    saved_path = default_storage.save(filename, ContentFile(pdf_bytes))

    export_record.status = ReceiverDataExport.Status.COMPLETED
    export_record.file_path = saved_path
    export_record.completed_at = timezone.now()
    export_record.save(update_fields=["status", "file_path", "completed_at"])

    _log_data_export(user, saved_path)

    download_path = "/api/v1/receiver/account/data-export/download/"
    if request is not None:
        download_url = request.build_absolute_uri(download_path)
    else:
        download_url = download_path

    return {
        "request_id": str(export_record.id),
        "phone_e164": user.phone_e164,
        "status": export_record.status,
        "requested_at": export_record.requested_at.isoformat(),
        "download_url": download_url,
        "format": "pdf",
    }


@transaction.atomic
def delete_receiver_account(user: User, confirmation: str) -> None:
    if confirmation != DELETE_CONFIRMATION_TEXT:
        raise PeonyAPIException(
            code="INVALID_CONFIRMATION",
            message='Type "DELETE" to confirm account deletion.',
            http_status=400,
        )

    if user.role != "RECEIVER":
        raise PeonyAPIException(
            code="ACCOUNT_DELETE_NOT_SUPPORTED",
            message="Account deletion is only supported for receiver accounts.",
            http_status=400,
        )

    profile = _get_receiver_profile(user)

    if profile.photo_url:
        delete_stored_photo(profile.photo_url)

    for export in ReceiverDataExport.objects.filter(user=user):
        if export.file_path and default_storage.exists(export.file_path):
            default_storage.delete(export.file_path)

    OutstandingToken.objects.filter(user=user).delete()
    user.delete()
