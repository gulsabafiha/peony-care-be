import uuid

from django.db import models

from apps.accounts.models import DonorProfile, RestaurantProfile, User
from apps.common.choices import (
    ClosedReason,
    FoodCategory,
    FoodStatus,
    ListStatus,
    RecurrenceType,
    SponsorshipType,
)


class FoodItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    restaurant = models.ForeignKey(
        RestaurantProfile,
        on_delete=models.CASCADE,
        related_name="food_items",
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=32, choices=FoodCategory.choices)
    unit = models.CharField(max_length=20, default="pack")
    photo_url = models.URLField(max_length=500, blank=True)
    quantity_original = models.IntegerField()
    quantity_available = models.IntegerField()
    quantity_claimed = models.IntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=FoodStatus.choices,
        default=FoodStatus.AVAILABLE,
    )
    list_status = models.CharField(
        max_length=20,
        choices=ListStatus.choices,
        default=ListStatus.ACTIVE,
    )
    pickup_start = models.DateTimeField()
    pickup_end = models.DateTimeField()
    recurrence_type = models.CharField(
        max_length=20,
        choices=RecurrenceType.choices,
        default=RecurrenceType.NONE,
    )
    recurrence_days = models.JSONField(default=list, blank=True)
    # Shared by every auto-posted listing in a DAILY/CUSTOM series.
    recurrence_series_id = models.UUIDField(null=True, blank=True, db_index=True)
    source_note = models.TextField(blank=True, default="")
    food_qr_data = models.CharField(max_length=200, blank=True)
    food_qr_image_url = models.URLField(max_length=500, blank=True)
    sponsorship_type = models.CharField(
        max_length=20,
        choices=SponsorshipType.choices,
        default=SponsorshipType.DIRECT,
    )
    individual_donor = models.ForeignKey(
        DonorProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sponsored_food_items",
    )
    sponsor_display_name = models.CharField(max_length=100, blank=True)
    meal_order_id = models.UUIDField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_reason = models.CharField(max_length=50, choices=ClosedReason.choices, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "food_items"
        indexes = [
            models.Index(fields=["list_status", "pickup_end"]),
            models.Index(fields=["restaurant", "list_status"]),
        ]

    def __str__(self) -> str:
        return self.name


class FoodReportReasonOption(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=50, unique=True)
    label = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "food_report_reason_options"
        ordering = ["sort_order", "label"]

    def __str__(self) -> str:
        return self.label


class FoodReport(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reporter = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="food_reports",
    )
    food_item = models.ForeignKey(
        FoodItem,
        on_delete=models.CASCADE,
        related_name="reports",
    )
    restaurant = models.ForeignKey(
        RestaurantProfile,
        on_delete=models.CASCADE,
        related_name="food_reports",
    )
    reason_option = models.ForeignKey(
        FoodReportReasonOption,
        on_delete=models.PROTECT,
        related_name="reports",
    )
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "food_reports"
        indexes = [
            models.Index(fields=["restaurant", "created_at"]),
            models.Index(fields=["food_item", "created_at"]),
            models.Index(fields=["reporter", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"Report on {self.food_item.name} by {self.reporter_id}"


class MenuItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    restaurant = models.ForeignKey(
        RestaurantProfile,
        on_delete=models.CASCADE,
        related_name="menu_items",
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price_sgd = models.DecimalField(max_digits=8, decimal_places=2)
    photo_url = models.URLField(max_length=500, blank=True)
    is_available = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    created_by_admin = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "menu_items"
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class MenuPhoto(models.Model):
    """Gallery photos of a restaurant menu board / dishes shown to donors."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    restaurant = models.ForeignKey(
        RestaurantProfile,
        on_delete=models.CASCADE,
        related_name="menu_photos",
    )
    photo_url = models.URLField(max_length=500)
    sort_order = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "menu_photos"
        ordering = ["sort_order", "created_at"]
        indexes = [
            models.Index(fields=["restaurant", "sort_order"]),
        ]

    def __str__(self) -> str:
        return f"MenuPhoto {self.sort_order} ({self.restaurant_id})"
