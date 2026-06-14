from django.contrib import admin

from apps.donations.models import FoodItem, MenuItem


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
