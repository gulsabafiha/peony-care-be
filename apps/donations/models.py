import uuid

from django.db import models

from apps.accounts.models import DonorProfile, RestaurantProfile
from apps.common.choices import (
    ClosedReason,
    FoodCategory,
    FoodStatus,
    ListStatus,
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
    category = models.CharField(max_length=20, choices=FoodCategory.choices)
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
