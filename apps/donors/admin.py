from django.contrib import admin

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
        from django.utils import timezone

        queryset.update(
            status="CONFIRMED",
            confirmed_at=timezone.now(),
            confirmed_by=request.user.username,
        )
