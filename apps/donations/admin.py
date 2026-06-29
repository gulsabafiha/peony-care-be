from django.contrib import admin

from apps.donations.models import FoodItem, FoodReport, FoodReportReasonOption, MenuItem


@admin.register(FoodItem)
class FoodItemAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "restaurant",
        "status",
        "list_status",
        "quantity_available",
        "pickup_end",
    )
    list_filter = ("status", "list_status", "category")
    search_fields = ("name", "restaurant__name")


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ("name", "restaurant", "price_sgd", "is_available", "sort_order")
    list_filter = ("is_available",)
    search_fields = ("name", "restaurant__name")


@admin.register(FoodReportReasonOption)
class FoodReportReasonOptionAdmin(admin.ModelAdmin):
    list_display = ("label", "code", "is_active", "sort_order", "updated_at")
    list_editable = ("is_active", "sort_order")
    list_filter = ("is_active",)
    search_fields = ("label", "code")
    ordering = ("sort_order", "label")


@admin.register(FoodReport)
class FoodReportAdmin(admin.ModelAdmin):
    list_display = (
        "food_item",
        "restaurant",
        "reporter",
        "reason_option",
        "created_at",
    )
    list_filter = ("reason_option", "created_at")
    search_fields = ("food_item__name", "restaurant__name", "reporter__phone_e164", "comment")
    readonly_fields = ("created_at",)
