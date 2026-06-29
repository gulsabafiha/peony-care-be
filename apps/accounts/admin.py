from django.contrib import admin

from apps.accounts.models import (
    DonorProfile,
    OtpChallenge,
    ReceiverLocationHistory,
    ReceiverProfile,
    RefreshToken,
    RestaurantProfile,
    User,
)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("phone_e164", "role", "is_active", "is_staff", "created_at")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("phone_e164",)
    ordering = ("-created_at",)


@admin.register(OtpChallenge)
class OtpChallengeAdmin(admin.ModelAdmin):
    list_display = ("phone_e164", "purpose", "attempts", "expires_at", "consumed_at")
    list_filter = ("purpose",)
    search_fields = ("phone_e164",)


@admin.register(RefreshToken)
class RefreshTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "expires_at", "revoked_at", "created_at")
    search_fields = ("user__phone_e164",)


@admin.register(ReceiverProfile)
class ReceiverProfileAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "user",
        "browse_radius_km",
        "location_services_enabled",
        "total_claims",
    )
    search_fields = ("display_name", "user__phone_e164")


@admin.register(ReceiverLocationHistory)
class ReceiverLocationHistoryAdmin(admin.ModelAdmin):
    list_display = ("place_name", "receiver", "place_type", "visited_at")
    list_filter = ("place_type",)
    search_fields = ("place_name", "area_label", "receiver__phone_e164")


@admin.register(RestaurantProfile)
class RestaurantProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "uen", "is_approved", "is_verified", "total_food_shared")
    list_filter = ("is_approved", "is_verified")
    search_fields = ("name", "uen", "user__phone_e164")


@admin.register(DonorProfile)
class DonorProfileAdmin(admin.ModelAdmin):
    list_display = ("display_name", "user", "credit_preference", "total_meals_sponsored")
    search_fields = ("display_name", "user__phone_e164")
