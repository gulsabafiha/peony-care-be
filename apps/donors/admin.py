from django.contrib import admin
from django.utils import timezone

from apps.common.choices import MoneyDonationStatus
from apps.donors.models import MealOrder, MealOrderItem, MoneyDonation


class MealOrderItemInline(admin.TabularInline):
    model = MealOrderItem
    extra = 0
    autocomplete_fields = ("menu_item",)


@admin.register(MealOrder)
class MealOrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "donor",
        "restaurant",
        "status",
        "total_amount_sgd",
        "credit_preference",
        "created_at",
    )
    list_filter = ("status", "credit_preference")
    search_fields = ("donor__display_name", "restaurant__name")
    readonly_fields = ("id", "created_at")
    autocomplete_fields = ("donor", "restaurant", "food_item")
    inlines = [MealOrderItemInline]
    ordering = ("-created_at",)


@admin.register(MealOrderItem)
class MealOrderItemAdmin(admin.ModelAdmin):
    list_display = ("meal_order", "menu_item", "quantity", "unit_price_sgd")
    search_fields = ("meal_order__id", "menu_item__name", "meal_order__donor__display_name")
    autocomplete_fields = ("meal_order", "menu_item")


@admin.register(MoneyDonation)
class MoneyDonationAdmin(admin.ModelAdmin):
    list_display = (
        "reference_code",
        "donor",
        "amount_sgd",
        "status",
        "is_anonymous",
        "created_at",
        "confirmed_at",
    )
    list_filter = ("status", "is_anonymous")
    search_fields = ("reference_code", "donor__display_name", "confirmed_by")
    readonly_fields = ("id", "created_at", "transfer_marked_at", "confirmed_at")
    autocomplete_fields = ("donor",)
    actions = ["confirm_donations"]
    ordering = ("-created_at",)

    @admin.action(description="Confirm selected PayNow transfers")
    def confirm_donations(self, request, queryset):
        now = timezone.now()
        pending = queryset.filter(status=MoneyDonationStatus.PENDING_TRANSFER)
        for donation in pending.select_related("donor"):
            donation.status = MoneyDonationStatus.CONFIRMED
            donation.confirmed_at = now
            donation.confirmed_by = request.user.username
            donation.save(
                update_fields=["status", "confirmed_at", "confirmed_by"],
            )
            donor = donation.donor
            donor.total_amount_donated_sgd += donation.amount_sgd
            donor.save(update_fields=["total_amount_donated_sgd"])
