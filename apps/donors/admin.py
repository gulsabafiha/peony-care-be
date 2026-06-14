from django.contrib import admin
from django.utils import timezone

from apps.common.choices import MoneyDonationStatus
from apps.donors.models import MealOrder, MealOrderItem, MoneyDonation


class MealOrderItemInline(admin.TabularInline):
    model = MealOrderItem
    extra = 0


@admin.register(MealOrder)
class MealOrderAdmin(admin.ModelAdmin):
    list_display = ("id", "donor", "restaurant", "status", "total_amount_sgd", "created_at")
    list_filter = ("status",)
    inlines = [MealOrderItemInline]


@admin.register(MoneyDonation)
class MoneyDonationAdmin(admin.ModelAdmin):
    list_display = ("reference_code", "donor", "amount_sgd", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("reference_code", "donor__display_name")
    actions = ["confirm_donations"]

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
