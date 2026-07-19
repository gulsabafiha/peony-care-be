from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

from apps.accounts.data_export_pdf import build_restaurant_data_pdf
from apps.accounts.models import (
    RestaurantDataExport,
    RestaurantLegalRetention,
    RestaurantPayoutRetention,
    RestaurantProfile,
    User,
)
from apps.claims.models import FoodClaim
from apps.common.choices import COUNTED_CLAIM_STATUSES, ClosedReason, ListStatus, UserRole
from apps.common.emailing import send_restaurant_data_export_email
from apps.common.exceptions import PeonyAPIException
from apps.common.timezone_utils import SGT
from apps.common.uploads import delete_stored_photo
from apps.donations.models import FoodItem, MenuPhoto
from apps.donors.models import MealOrder
from apps.notifications.models import Notification, NotificationSettings
from apps.notifications.settings_services import serialize_notification_settings

logger = logging.getLogger(__name__)

DELETE_CONFIRMATION_TEXT = "DELETE"
DATA_EXPORT_COOLDOWN_HOURS = 48


def _get_restaurant_profile(user: User) -> RestaurantProfile:
    try:
        return user.restaurant_profile
    except RestaurantProfile.DoesNotExist as exc:
        raise PeonyAPIException(
            code="PROFILE_NOT_FOUND",
            message="Restaurant profile not found.",
            http_status=404,
        ) from exc


def _analytics_summary(restaurant: RestaurantProfile) -> dict:
    people_fed = (
        FoodClaim.objects.filter(
            restaurant=restaurant,
            status__in=COUNTED_CLAIM_STATUSES,
        ).aggregate(total=Sum("quantity_claimed"))["total"]
        or 0
    )
    donations = FoodItem.objects.filter(restaurant=restaurant)
    donations_posted = donations.count()
    total_original = donations.aggregate(total=Sum("quantity_original"))["total"] or 0
    claim_rate_pct = round((people_fed / total_original) * 100) if total_original else None
    sponsored = MealOrder.objects.filter(restaurant=restaurant).aggregate(
        total=Sum("total_amount_sgd")
    )["total"] or Decimal("0.00")
    return {
        "people_fed": people_fed,
        "donations_posted": donations_posted,
        "claim_rate_pct": claim_rate_pct,
        "sponsored_sgd": str(Decimal(sponsored).quantize(Decimal("0.01"))),
    }


def build_restaurant_data_export(user: User) -> dict:
    profile = _get_restaurant_profile(user)
    foods = FoodItem.objects.filter(restaurant=profile).order_by("-created_at")
    claims = (
        FoodClaim.objects.filter(restaurant=profile)
        .select_related("food", "receiver")
        .order_by("-claimed_at")
    )
    meal_orders = (
        MealOrder.objects.filter(restaurant=profile)
        .select_related("donor")
        .prefetch_related("items__menu_item")
        .order_by("-created_at")
    )

    settings_obj = NotificationSettings.objects.filter(user=user).first()
    notification_settings = (
        serialize_notification_settings(settings_obj) if settings_obj else None
    )
    if notification_settings:
        notification_settings.pop("updated_at", None)

    analytics = _analytics_summary(profile)

    return {
        "exported_at": timezone.now().isoformat(),
        "profile": {
            "id": str(profile.id),
            "name": profile.name,
            "phone": user.phone_e164,
            "uen": profile.uen,
            "address": profile.address,
            "contact_name": profile.contact_name,
            "contact_email": profile.contact_email,
            "contact_phone": profile.contact_phone,
            "cuisine": profile.cuisine,
            "opening_hours": profile.opening_hours,
            "about": profile.about,
            "photo_url": profile.photo_url or None,
            "member_since": profile.created_at.astimezone(SGT).strftime("%b %Y"),
            "is_approved": profile.is_approved,
            "is_verified": profile.is_verified,
            "stats": {
                "people_fed": analytics["people_fed"],
                "donations_posted": analytics["donations_posted"],
                "claim_rate_pct": analytics["claim_rate_pct"],
            },
        },
        "donations": [
            {
                "id": str(food.id),
                "name": food.name,
                "category": food.category,
                "quantity_original": food.quantity_original,
                "quantity_remaining": food.quantity_available,
                "status": food.status,
                "list_status": food.list_status,
                "created_at": food.created_at.isoformat(),
            }
            for food in foods
        ],
        "claims": [
            {
                "id": str(claim.id),
                "food_name": claim.food.name,
                "receiver_phone": claim.receiver.phone_e164,
                "status": claim.status,
                "quantity_claimed": claim.quantity_claimed,
                "claimed_at": claim.claimed_at.isoformat(),
                "claim_date": claim.claim_date.isoformat(),
            }
            for claim in claims
        ],
        "sponsored_orders": [
            {
                "id": str(order.id),
                "status": order.status,
                "total_amount_sgd": str(order.total_amount_sgd),
                "credit_preference": order.credit_preference,
                "donor_label": order.donor.display_name if order.donor_id else "",
                "ordered_at": order.created_at.isoformat(),
                "items": [
                    {
                        "name": item.menu_item.name,
                        "quantity": item.quantity,
                        "unit_price_sgd": str(item.unit_price_sgd),
                    }
                    for item in order.items.all()
                ],
            }
            for order in meal_orders
        ],
        "analytics": analytics,
        "notification_settings": notification_settings,
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
        "[Peony Restaurant Data Export] %s (%s) | file=%s",
        user.phone_e164,
        user.id,
        download_url,
    )


def generate_data_export_pdf(user: User) -> bytes:
    _get_restaurant_profile(user)
    return build_restaurant_data_pdf(user)


@transaction.atomic
def request_data_export(user: User, request=None) -> dict:
    profile = _get_restaurant_profile(user)
    cutoff = timezone.now() - timedelta(hours=DATA_EXPORT_COOLDOWN_HOURS)
    if RestaurantDataExport.objects.filter(user=user, requested_at__gte=cutoff).exists():
        raise PeonyAPIException(
            code="EXPORT_ALREADY_REQUESTED",
            message="A data export was requested recently. Please try again later.",
            http_status=429,
        )

    business_email = (profile.contact_email or "").strip()
    export_record = RestaurantDataExport.objects.create(
        user=user,
        phone_e164=user.phone_e164,
        email=business_email,
        status=RestaurantDataExport.Status.PENDING,
    )

    pdf_bytes = build_restaurant_data_pdf(user)
    filename = f"exports/restaurants/{user.id}/{export_record.id}.pdf"
    saved_path = default_storage.save(filename, ContentFile(pdf_bytes))

    download_path = "/api/v1/restaurant/account/data-export/download/"
    if request is not None:
        download_url = request.build_absolute_uri(download_path)
    else:
        download_url = download_path

    email_sent = send_restaurant_data_export_email(
        to_email=business_email,
        restaurant_name=profile.name,
        download_url=download_url,
    )

    export_record.status = RestaurantDataExport.Status.COMPLETED
    export_record.file_path = saved_path
    export_record.email_sent = email_sent
    export_record.completed_at = timezone.now()
    export_record.save(
        update_fields=["status", "file_path", "email_sent", "completed_at"]
    )

    _log_data_export(user, saved_path)

    eta_hours = int(getattr(settings, "DATA_EXPORT_EMAIL_ETA_HOURS", 48))
    return {
        "request_id": str(export_record.id),
        "phone_e164": user.phone_e164,
        "email": business_email or None,
        "status": export_record.status,
        "requested_at": export_record.requested_at.isoformat(),
        "download_url": download_url,
        "format": "pdf",
        "delivery": "email",
        "email_sent": email_sent,
        "eta_hours": eta_hours,
        "message": (
            f"Sent to your business email. We'll send a secure download link within "
            f"{eta_hours} hours."
            if business_email
            else "Export ready. Add a business email on your profile to receive the link by email."
        ),
        "includes": [
            "Business profile (name, UEN, address, hours)",
            "Contact details (name, email, mobile)",
            "Donation and claim history",
            "Sponsored-order and payout records",
            "Analytics summary",
        ],
    }


def _deactivate_active_donations(restaurant: RestaurantProfile) -> int:
    now = timezone.now()
    active = FoodItem.objects.filter(restaurant=restaurant, list_status=ListStatus.ACTIVE)
    count = active.count()
    active.update(
        list_status=ListStatus.INACTIVE,
        closed_at=now,
        closed_reason=ClosedReason.MANUAL,
        updated_at=now,
    )
    return count


def _snapshot_payouts(
    restaurant: RestaurantProfile,
    legal: RestaurantLegalRetention,
    retained_until,
) -> int:
    orders = (
        MealOrder.objects.filter(restaurant=restaurant)
        .select_related("donor")
        .prefetch_related("items__menu_item")
    )
    created = 0
    for order in orders:
        RestaurantPayoutRetention.objects.create(
            legal_retention=legal,
            former_meal_order_id=order.id,
            former_restaurant_id=restaurant.id,
            restaurant_uen=restaurant.uen,
            restaurant_name=restaurant.name,
            donor_label=order.donor.display_name if order.donor_id else "",
            total_amount_sgd=order.total_amount_sgd,
            credit_preference=order.credit_preference,
            status=order.status,
            ordered_at=order.created_at,
            items=[
                {
                    "name": item.menu_item.name,
                    "quantity": item.quantity,
                    "unit_price_sgd": str(item.unit_price_sgd),
                }
                for item in order.items.all()
            ],
            retained_until=retained_until,
        )
        created += 1
    return created


@transaction.atomic
def delete_restaurant_account(user: User, confirmation: str) -> dict:
    if confirmation != DELETE_CONFIRMATION_TEXT:
        raise PeonyAPIException(
            code="INVALID_CONFIRMATION",
            message='Type "DELETE" to confirm account deletion.',
            http_status=400,
        )

    if user.role != UserRole.RESTAURANT:
        raise PeonyAPIException(
            code="ACCOUNT_DELETE_NOT_SUPPORTED",
            message="Account deletion is only supported for restaurant accounts on this endpoint.",
            http_status=400,
        )

    profile = _get_restaurant_profile(user)
    now = timezone.now()
    uen_days = int(getattr(settings, "RESTAURANT_UEN_RETENTION_DAYS", 90))
    payout_years = int(getattr(settings, "RESTAURANT_PAYOUT_RETENTION_YEARS", 7))
    purge_after = now + timedelta(days=uen_days)
    payout_until = now + relativedelta(years=payout_years)

    deactivated = _deactivate_active_donations(profile)

    legal = RestaurantLegalRetention.objects.create(
        former_user_id=user.id,
        former_restaurant_id=profile.id,
        phone_e164=user.phone_e164,
        uen=profile.uen,
        business_name=profile.name,
        contact_name=profile.contact_name,
        contact_email=profile.contact_email,
        contact_phone=profile.contact_phone,
        deleted_at=now,
        purge_after=purge_after,
    )
    payouts_retained = _snapshot_payouts(profile, legal, payout_until)

    # Snapshots are kept; remove live orders so MenuItem PROTECT does not block delete.
    MealOrder.objects.filter(restaurant=profile).delete()

    if profile.photo_url:
        delete_stored_photo(profile.photo_url)

    for photo in MenuPhoto.objects.filter(restaurant=profile):
        if photo.photo_url:
            delete_stored_photo(photo.photo_url)

    for food in FoodItem.objects.filter(restaurant=profile):
        if food.photo_url:
            delete_stored_photo(food.photo_url)

    for export in RestaurantDataExport.objects.filter(user=user):
        if export.file_path and default_storage.exists(export.file_path):
            default_storage.delete(export.file_path)

    OutstandingToken.objects.filter(user=user).delete()
    user.delete()

    return {
        "deleted": True,
        "active_donations_deactivated": deactivated,
        "retention": {
            "uen_contact_days": uen_days,
            "uen_contact_retained_until": purge_after.isoformat(),
            "payout_years": payout_years,
            "payout_records_retained": payouts_retained,
            "payout_retained_until": payout_until.isoformat(),
            "summary": [
                "Restaurant profile, address, hours, and dish photos deleted",
                f"UEN and contact details retained for {uen_days} days for tax records",
                "Donation history and analytics deleted",
                "Active donations deactivated before deletion",
                f"Sponsored donation payout records retained for {payout_years} years (ACRA)",
            ],
        },
    }
