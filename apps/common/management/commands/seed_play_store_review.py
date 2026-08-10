"""Seed Play Store reviewer accounts (fixed OTP 1234, no SMS)."""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import ReceiverProfile, RestaurantProfile, User
from apps.accounts.play_store_review import review_otp_code, review_phone_set
from apps.common.choices import UserRole
from apps.common.phone import normalize_phone_e164

# Defaults align with PLAY_STORE_REVIEW_PHONES in settings.
REVIEW_RECEIVER_PHONE = "+6599990001"
REVIEW_RESTAURANT_PHONE = "+6599990002"


class Command(BaseCommand):
    help = (
        "Create Play Store reviewer accounts. "
        "These phones accept the fixed OTP (default 1234) without SMS."
    )

    def handle(self, *args, **options):
        configured = review_phone_set()
        receiver_phone = normalize_phone_e164(REVIEW_RECEIVER_PHONE)
        restaurant_phone = normalize_phone_e164(REVIEW_RESTAURANT_PHONE)

        if receiver_phone not in configured or restaurant_phone not in configured:
            self.stdout.write(
                self.style.WARNING(
                    "Ensure PLAY_STORE_REVIEW_PHONES includes "
                    f"{receiver_phone} and {restaurant_phone}."
                )
            )

        with transaction.atomic():
            receiver = self._seed_receiver(receiver_phone)
            restaurant = self._seed_restaurant(restaurant_phone)

        otp = review_otp_code()
        self.stdout.write(self.style.SUCCESS("Play Store review accounts ready."))
        self.stdout.write(f"  OTP (no SMS): {otp}")
        self.stdout.write(
            f"  Receiver:   {receiver.user.phone_e164}  ({receiver.display_name})"
        )
        self.stdout.write(
            f"  Restaurant: {restaurant.user.phone_e164}  ({restaurant.name})"
        )
        self.stdout.write(
            f"  Configured review phones: {', '.join(sorted(configured)) or '(none)'}"
        )
        self.stdout.write(
            f"  PLAY_STORE_REVIEW_OTP={getattr(settings, 'PLAY_STORE_REVIEW_OTP', otp)}"
        )

    def _seed_receiver(self, phone: str) -> ReceiverProfile:
        user, _ = User.objects.get_or_create(
            phone_e164=phone,
            defaults={"role": UserRole.RECEIVER, "is_active": True},
        )
        if not user.is_active or user.role != UserRole.RECEIVER:
            user.is_active = True
            user.role = UserRole.RECEIVER
            user.save(update_fields=["is_active", "role", "updated_at"])

        profile, created = ReceiverProfile.objects.get_or_create(
            user=user,
            defaults={
                "display_name": "Play Store Reviewer",
                "latitude": 1.3521,
                "longitude": 103.8198,
                "browse_radius_km": 5.0,
            },
        )
        if not created and profile.display_name != "Play Store Reviewer":
            profile.display_name = "Play Store Reviewer"
            profile.save(update_fields=["display_name"])
        return profile

    def _seed_restaurant(self, phone: str) -> RestaurantProfile:
        user, _ = User.objects.get_or_create(
            phone_e164=phone,
            defaults={"role": UserRole.RESTAURANT, "is_active": True},
        )
        if not user.is_active or user.role != UserRole.RESTAURANT:
            user.is_active = True
            user.role = UserRole.RESTAURANT
            user.save(update_fields=["is_active", "role", "updated_at"])

        profile, created = RestaurantProfile.objects.get_or_create(
            user=user,
            defaults={
                "name": "UduFood Demo Kitchen",
                "uen": "T00SS0001A",
                "address": "1 Fullerton Road, Singapore 049213",
                "postal_code": "049213",
                "latitude": 1.2863,
                "longitude": 103.8545,
                "contact_name": "Play Store Reviewer",
                "contact_email": "review@udufood.com",
                "contact_phone": phone,
                "cuisine": "Mixed",
                "about": "Demo restaurant for Google Play review.",
                "is_approved": True,
                "is_verified": True,
                "approved_at": timezone.now(),
            },
        )
        if not created:
            profile.is_approved = True
            profile.is_verified = True
            if profile.approved_at is None:
                profile.approved_at = timezone.now()
            profile.save(
                update_fields=["is_approved", "is_verified", "approved_at"]
            )
        return profile
