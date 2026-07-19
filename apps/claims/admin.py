from django.contrib import admin

from apps.claims.models import ClaimReport, ClaimReportReasonOption, FoodClaim


@admin.register(FoodClaim)
class FoodClaimAdmin(admin.ModelAdmin):
    list_display = (
        "food",
        "receiver",
        "restaurant",
        "claim_date",
        "status",
        "quantity_claimed",
        "claimed_at",
    )
    list_filter = ("status", "claim_date")
    search_fields = ("receiver__phone_e164", "food__name", "restaurant__name")
    readonly_fields = ("id", "created_at", "claimed_at", "collected_at", "no_show_at")
    autocomplete_fields = ("food", "receiver", "restaurant")
    ordering = ("-claimed_at",)
    date_hierarchy = "claim_date"


@admin.register(ClaimReportReasonOption)
class ClaimReportReasonOptionAdmin(admin.ModelAdmin):
    list_display = ("label", "code", "is_active", "sort_order", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("code", "label")
    list_editable = ("is_active", "sort_order")
    ordering = ("sort_order", "label")


@admin.register(ClaimReport)
class ClaimReportAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "restaurant",
        "claim",
        "reported_receiver",
        "reason_option",
        "created_at",
    )
    list_filter = ("reason_option", "created_at")
    search_fields = (
        "restaurant__name",
        "reported_receiver__phone_e164",
        "comment",
    )
    readonly_fields = ("id", "created_at")
    autocomplete_fields = (
        "reporter",
        "claim",
        "restaurant",
        "reported_receiver",
        "reason_option",
    )
    ordering = ("-created_at",)
