from django.contrib import admin

from apps.donations.models import FoodItem, FoodReport, FoodReportReasonOption, MenuItem


@admin.register(FoodItem)
class FoodItemAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "restaurant",
        "status",
        "list_status",
        "category",
        "quantity_available",
        "pickup_start",
        "pickup_end",
        "created_at",
    )
    list_filter = ("status", "list_status", "category", "sponsorship_type")
    search_fields = ("name", "restaurant__name", "food_qr_data")
    readonly_fields = ("id", "created_at", "updated_at", "closed_at")
    autocomplete_fields = ("restaurant", "individual_donor")
    ordering = ("-created_at",)
    date_hierarchy = "pickup_start"


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ("name", "restaurant", "price_sgd", "is_available", "sort_order", "created_at")
    list_filter = ("is_available", "created_by_admin")
    search_fields = ("name", "restaurant__name")
    readonly_fields = ("id", "created_at")
    autocomplete_fields = ("restaurant",)
    list_editable = ("is_available", "sort_order")
    ordering = ("sort_order", "name")


@admin.register(FoodReportReasonOption)
class FoodReportReasonOptionAdmin(admin.ModelAdmin):
    list_display = ("label", "code", "is_active", "sort_order", "updated_at")
    list_editable = ("is_active", "sort_order")
    list_filter = ("is_active",)
    search_fields = ("label", "code")
    readonly_fields = ("id", "created_at", "updated_at")
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
    readonly_fields = ("id", "created_at")
    autocomplete_fields = ("reporter", "food_item", "restaurant", "reason_option")
    ordering = ("-created_at",)
