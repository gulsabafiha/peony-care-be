import uuid

from django.conf import settings
from django.db import models

from apps.accounts.models import RestaurantProfile
from apps.common.choices import ClaimStatus
from apps.donations.models import FoodItem


class FoodClaim(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    food = models.ForeignKey(FoodItem, on_delete=models.CASCADE, related_name="claims")
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="food_claims",
    )
    restaurant = models.ForeignKey(
        RestaurantProfile,
        on_delete=models.CASCADE,
        related_name="food_claims",
    )
    claim_date = models.DateField()
    claimed_at = models.DateTimeField()
    collected_at = models.DateTimeField(null=True, blank=True)
    no_show_at = models.DateTimeField(null=True, blank=True)
    receiver_lat = models.DecimalField(max_digits=10, decimal_places=7)
    receiver_lng = models.DecimalField(max_digits=10, decimal_places=7)
    status = models.CharField(
        max_length=20,
        choices=ClaimStatus.choices,
        default=ClaimStatus.CLAIMED,
    )
    quantity_claimed = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "food_claims"
        indexes = [
            models.Index(fields=["receiver", "claim_date"]),
            models.Index(fields=["food", "-claimed_at"]),
            models.Index(fields=["restaurant", "claim_date"]),
        ]

    def __str__(self) -> str:
        return f"Claim {self.id} ({self.status})"


class ClaimReportReasonOption(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=50, unique=True)
    label = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "claim_report_reason_options"
        ordering = ["sort_order", "label"]

    def __str__(self) -> str:
        return self.label


class ClaimReport(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="claim_reports",
    )
    claim = models.ForeignKey(
        FoodClaim,
        on_delete=models.CASCADE,
        related_name="reports",
    )
    restaurant = models.ForeignKey(
        RestaurantProfile,
        on_delete=models.CASCADE,
        related_name="claim_reports",
    )
    reported_receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="claim_reports_received",
    )
    reason_option = models.ForeignKey(
        ClaimReportReasonOption,
        on_delete=models.PROTECT,
        related_name="reports",
    )
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "claim_reports"
        indexes = [
            models.Index(fields=["restaurant", "created_at"]),
            models.Index(fields=["claim", "created_at"]),
            models.Index(fields=["reported_receiver", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"ClaimReport {self.id}"
