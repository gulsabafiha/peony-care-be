import uuid

from django.db import models

from apps.accounts.models import DonorProfile, RestaurantProfile
from apps.common.choices import (
    CreditPreference,
    MealOrderStatus,
    MoneyDonationStatus,
)
from apps.donations.models import FoodItem, MenuItem


class MealOrder(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    donor = models.ForeignKey(DonorProfile, on_delete=models.CASCADE, related_name="meal_orders")
    restaurant = models.ForeignKey(
        RestaurantProfile,
        on_delete=models.CASCADE,
        related_name="meal_orders",
    )
    food_item = models.ForeignKey(
        FoodItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="meal_orders",
    )
    total_amount_sgd = models.DecimalField(max_digits=10, decimal_places=2)
    credit_preference = models.CharField(max_length=20, choices=CreditPreference.choices)
    status = models.CharField(
        max_length=20,
        choices=MealOrderStatus.choices,
        default=MealOrderStatus.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "meal_orders"

    def __str__(self) -> str:
        return f"MealOrder {self.id}"


class MealOrderItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meal_order = models.ForeignKey(MealOrder, on_delete=models.CASCADE, related_name="items")
    menu_item = models.ForeignKey(MenuItem, on_delete=models.PROTECT, related_name="order_items")
    quantity = models.IntegerField()
    unit_price_sgd = models.DecimalField(max_digits=8, decimal_places=2)

    class Meta:
        db_table = "meal_order_items"

    def __str__(self) -> str:
        return f"{self.menu_item.name} x{self.quantity}"


class MoneyDonation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    donor = models.ForeignKey(
        DonorProfile,
        on_delete=models.CASCADE,
        related_name="money_donations",
    )
    amount_sgd = models.DecimalField(max_digits=10, decimal_places=2)
    reference_code = models.CharField(max_length=20, unique=True)
    is_anonymous = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=MoneyDonationStatus.choices,
        default=MoneyDonationStatus.PENDING_TRANSFER,
    )
    transfer_marked_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "money_donations"

    def __str__(self) -> str:
        return self.reference_code
