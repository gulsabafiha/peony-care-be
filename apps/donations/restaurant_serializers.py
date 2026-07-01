from rest_framework import serializers

from apps.common.choices import FoodCategory


class CreateDonationSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    category = serializers.ChoiceField(choices=FoodCategory.choices)
    unit = serializers.CharField(max_length=20, required=False, default="pack")
    photo_url = serializers.URLField(required=False, allow_blank=True, default="")
    quantity = serializers.IntegerField(min_value=1)
    pickup_start = serializers.DateTimeField()
    pickup_end = serializers.DateTimeField()


class UpdateDonationSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    category = serializers.ChoiceField(choices=FoodCategory.choices, required=False)
    unit = serializers.CharField(max_length=20, required=False)
    photo_url = serializers.URLField(required=False, allow_blank=True)
    quantity = serializers.IntegerField(min_value=1, required=False)
    pickup_start = serializers.DateTimeField(required=False)
    pickup_end = serializers.DateTimeField(required=False)


class DonationListQuerySerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=["active", "past", "inactive"],
        default="active",
    )


class RestaurantDonationSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    status = serializers.CharField()
    list_status = serializers.CharField()
    quantity_available = serializers.IntegerField()
    food_qr_data = serializers.CharField()


class DashboardSerializer(serializers.Serializer):
    lives_impacted = serializers.IntegerField()
    donations_this_year = serializers.IntegerField()
    claim_rate_pct = serializers.IntegerField()
    active_count = serializers.IntegerField()
    claimed_today = serializers.IntegerField()


class RestaurantProfileSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    address = serializers.CharField()
    is_approved = serializers.BooleanField(required=False)


class RestaurantProfileUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200, required=False)
    address = serializers.CharField(required=False)
    contact_name = serializers.CharField(max_length=100, required=False)
    contact_email = serializers.EmailField(required=False, allow_blank=True)
    contact_phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    opening_hours = serializers.CharField(required=False, allow_blank=True)
    about = serializers.CharField(required=False, allow_blank=True)
    photo_url = serializers.URLField(required=False, allow_blank=True)
    latitude = serializers.FloatField(min_value=-90, max_value=90, required=False)
    longitude = serializers.FloatField(min_value=-180, max_value=180, required=False)

    def validate(self, data):
        lat = data.get("latitude")
        lng = data.get("longitude")
        if (lat is None) != (lng is None):
            raise serializers.ValidationError(
                {"latitude": "latitude and longitude must be provided together."}
            )
        return data


class ApprovalStatusSerializer(serializers.Serializer):
    is_approved = serializers.BooleanField()
    is_verified = serializers.BooleanField()
    submitted_at = serializers.DateTimeField()
