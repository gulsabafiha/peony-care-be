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
