from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.accounts.models import (
    DonorProfile,
    OtpChallenge,
    ReceiverDataExport,
    ReceiverLocationHistory,
    ReceiverProfile,
    RefreshToken,
    RestaurantProfile,
    User,
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("-created_at",)
    list_display = ("phone_e164", "role", "is_active", "is_staff", "is_superuser", "created_at")
    list_filter = ("role", "is_active", "is_staff", "is_superuser")
    search_fields = ("phone_e164",)
    readonly_fields = ("id", "created_at", "updated_at", "last_login")
    filter_horizontal = ("groups", "user_permissions")

    fieldsets = (
        (None, {"fields": ("phone_e164", "password")}),
        ("Role & status", {"fields": ("role", "is_active", "is_staff", "is_superuser")}),
        ("Permissions", {"fields": ("groups", "user_permissions")}),
        ("Timestamps", {"fields": ("last_login", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "phone_e164",
                    "role",
                    "password1",
                    "password2",
                    "is_staff",
                    "is_superuser",
                ),
            },
        ),
    )


@admin.register(OtpChallenge)
class OtpChallengeAdmin(admin.ModelAdmin):
    list_display = ("phone_e164", "purpose", "attempts", "expires_at", "consumed_at", "created_at")
    list_filter = ("purpose", "consumed_at")
    search_fields = ("phone_e164",)
    readonly_fields = ("id", "code_hash", "created_at")
    ordering = ("-created_at",)


@admin.register(RefreshToken)
class RefreshTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "expires_at", "revoked_at", "created_at")
    list_filter = ("revoked_at",)
    search_fields = ("user__phone_e164",)
    readonly_fields = ("id", "token_hash", "created_at")
    autocomplete_fields = ("user",)
    ordering = ("-created_at",)


@admin.register(ReceiverProfile)
class ReceiverProfileAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "user",
        "browse_radius_km",
        "location_services_enabled",
        "total_claims",
        "created_at",
    )
    list_filter = ("location_services_enabled", "save_location_history")
    search_fields = ("display_name", "user__phone_e164")
    readonly_fields = ("id", "created_at")
    autocomplete_fields = ("user",)


@admin.register(ReceiverLocationHistory)
class ReceiverLocationHistoryAdmin(admin.ModelAdmin):
    list_display = ("place_name", "receiver", "place_type", "latitude", "longitude", "visited_at")
    list_filter = ("place_type",)
    search_fields = ("place_name", "area_label", "receiver__phone_e164")
    readonly_fields = ("id",)
    autocomplete_fields = ("receiver",)
    ordering = ("-visited_at",)


@admin.register(ReceiverDataExport)
class ReceiverDataExportAdmin(admin.ModelAdmin):
    list_display = ("user", "phone_e164", "status", "requested_at", "completed_at")
    list_filter = ("status",)
    search_fields = ("user__phone_e164", "phone_e164")
    readonly_fields = ("id", "requested_at")
    autocomplete_fields = ("user",)
    ordering = ("-requested_at",)


@admin.register(RestaurantProfile)
class RestaurantProfileAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "uen",
        "user",
        "is_approved",
        "is_verified",
        "total_food_shared",
        "created_at",
    )
    list_filter = ("is_approved", "is_verified")
    search_fields = ("name", "uen", "address", "user__phone_e164", "contact_name")
    readonly_fields = ("id", "created_at", "approved_at")
    autocomplete_fields = ("user",)
    actions = ("approve_restaurants", "verify_restaurants")

    @admin.action(description="Approve selected restaurants")
    def approve_restaurants(self, request, queryset):
        from django.utils import timezone

        queryset.update(is_approved=True, approved_at=timezone.now())

    @admin.action(description="Mark selected restaurants as verified")
    def verify_restaurants(self, request, queryset):
        queryset.update(is_verified=True)


@admin.register(DonorProfile)
class DonorProfileAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "user",
        "credit_preference",
        "total_meals_sponsored",
        "total_amount_donated_sgd",
        "created_at",
    )
    list_filter = ("credit_preference",)
    search_fields = ("display_name", "contact_email", "user__phone_e164")
    readonly_fields = ("id", "created_at")
    autocomplete_fields = ("user",)
