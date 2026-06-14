from django.contrib import admin

from apps.claims.models import FoodClaim


@admin.register(FoodClaim)
class FoodClaimAdmin(admin.ModelAdmin):
    list_display = ("food", "receiver", "restaurant", "claim_date", "status", "claimed_at")
    list_filter = ("status", "claim_date")
    search_fields = ("receiver__phone_e164", "food__name", "restaurant__name")
