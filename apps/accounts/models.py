import uuid

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from apps.accounts.managers import UserManager
from apps.common.choices import CreditPreference, LocationPlaceType, OtpPurpose, UserRole


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone_e164 = models.CharField(max_length=20, unique=True)
    role = models.CharField(max_length=20, choices=UserRole.choices)
    is_active = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "phone_e164"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        db_table = "users"

    def __str__(self) -> str:
        return self.phone_e164


class OtpChallenge(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone_e164 = models.CharField(max_length=20, db_index=True)
    code_hash = models.CharField(max_length=128)
    purpose = models.CharField(max_length=20, choices=OtpPurpose.choices)
    attempts = models.SmallIntegerField(default=0)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "otp_challenges"
        indexes = [
            models.Index(fields=["phone_e164", "purpose"]),
        ]

    def __str__(self) -> str:
        return f"{self.phone_e164} ({self.purpose})"


class RefreshToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="refresh_tokens")
    token_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "refresh_tokens"
        indexes = [
            models.Index(fields=["user", "expires_at"]),
        ]

    def __str__(self) -> str:
        return f"RefreshToken({self.user_id})"


class ReceiverProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="receiver_profile")
    display_name = models.CharField(max_length=100)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    browse_radius_km = models.FloatField(default=5.0)
    location_services_enabled = models.BooleanField(default=True)
    save_location_history = models.BooleanField(default=True)
    photo_url = models.URLField(max_length=500, blank=True)
    total_claims = models.IntegerField(default=0)
    last_claim_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "receiver_profiles"

    def __str__(self) -> str:
        return self.display_name


class ReceiverLocationHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    receiver = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="location_history",
    )
    place_name = models.CharField(max_length=200)
    area_label = models.CharField(max_length=300)
    place_type = models.CharField(
        max_length=20,
        choices=LocationPlaceType.choices,
        default=LocationPlaceType.OTHER,
    )
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    visited_at = models.DateTimeField()

    class Meta:
        db_table = "receiver_location_history"
        ordering = ["-visited_at"]
        indexes = [
            models.Index(fields=["receiver", "visited_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.place_name} ({self.receiver_id})"


class ReceiverDataExport(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="data_exports",
    )
    phone_e164 = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    file_path = models.CharField(max_length=500, blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "receiver_data_exports"
        ordering = ["-requested_at"]
        indexes = [
            models.Index(fields=["user", "requested_at"]),
        ]

    def __str__(self) -> str:
        return f"DataExport({self.user_id}, {self.status})"


class RestaurantProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="restaurant_profile")
    name = models.CharField(max_length=200)
    uen = models.CharField(max_length=20, unique=True)
    address = models.TextField()
    postal_code = models.CharField(max_length=10)
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    contact_name = models.CharField(max_length=100)
    contact_email = models.EmailField(max_length=254, blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    opening_hours = models.TextField(blank=True)
    about = models.TextField(blank=True)
    photo_url = models.URLField(max_length=500, blank=True)
    is_approved = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    approved_at = models.DateTimeField(null=True, blank=True)
    total_food_shared = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "restaurant_profiles"

    def __str__(self) -> str:
        return self.name


class DonorProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="donor_profile")
    display_name = models.CharField(max_length=100)
    contact_email = models.EmailField(max_length=254, blank=True)
    photo_url = models.URLField(max_length=500, blank=True)
    credit_preference = models.CharField(
        max_length=20,
        choices=CreditPreference.choices,
        default=CreditPreference.SHOW_NAME,
    )
    total_meals_sponsored = models.IntegerField(default=0)
    total_amount_donated_sgd = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "donor_profiles"

    def __str__(self) -> str:
        return self.display_name
