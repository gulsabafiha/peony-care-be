from rest_framework import serializers

from apps.common.choices import FoodCategory


class LocationQuerySerializer(serializers.Serializer):
    lat = serializers.FloatField(required=False)
    lng = serializers.FloatField(required=False)
    radius_km = serializers.FloatField(required=False, min_value=0.1, max_value=50)

    def validate(self, data):
        lat = data.get("lat")
        lng = data.get("lng")
        if (lat is None) != (lng is None):
            raise serializers.ValidationError("lat and lng must be provided together.")
        return data


class SearchQuerySerializer(LocationQuerySerializer):
    q = serializers.CharField(required=False, allow_blank=True, default="")
    category = serializers.ChoiceField(
        choices=FoodCategory.choices,
        required=False,
        allow_null=True,
    )


class FoodBrowseItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    category = serializers.CharField()
    distance_km = serializers.FloatField()
    quantity_available = serializers.IntegerField()
    pickup_window = serializers.CharField()
    restaurant = serializers.DictField()


class ClaimProgressSerializer(serializers.Serializer):
    claimed = serializers.IntegerField()
    total = serializers.IntegerField()
    remaining = serializers.IntegerField()
    percent_claimed = serializers.IntegerField()


class FoodDetailSerializer(FoodBrowseItemSerializer):
    claim_progress = ClaimProgressSerializer()


class RestaurantBrowseItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    address = serializers.CharField()
    postal_code = serializers.CharField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    photo_url = serializers.CharField(allow_null=True)
    is_verified = serializers.BooleanField()
    distance_km = serializers.FloatField()
    active_meal_count = serializers.IntegerField()


class RestaurantMealSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    description = serializers.CharField()
    category = serializers.CharField()
    photo_url = serializers.CharField(allow_null=True)
    quantity_available = serializers.IntegerField()
    pickup_start = serializers.CharField()
    pickup_end = serializers.CharField()
    pickup_window = serializers.CharField()
    sponsorship_type = serializers.CharField()
    sponsor_display_name = serializers.CharField(allow_null=True)


class ReceiverRestaurantDetailSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    address = serializers.CharField()
    postal_code = serializers.CharField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    photo_url = serializers.CharField(allow_null=True)
    about = serializers.CharField()
    opening_hours = serializers.CharField()
    contact_phone = serializers.CharField()
    is_verified = serializers.BooleanField()
    distance_km = serializers.FloatField()
    active_meal_count = serializers.IntegerField()
    categories = serializers.ListField(child=serializers.CharField())
    available_meals = RestaurantMealSummarySerializer(many=True)


class SubmitFoodReportSerializer(serializers.Serializer):
    reason_id = serializers.UUIDField()
    comment = serializers.CharField(required=False, allow_blank=True, default="")


class FoodReportReasonSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    code = serializers.CharField()
    label = serializers.CharField()


class FoodReportResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    food_id = serializers.UUIDField()
    food_name = serializers.CharField()
    restaurant_id = serializers.UUIDField()
    restaurant_name = serializers.CharField()
    reason_id = serializers.UUIDField()
    reason_code = serializers.CharField()
    reason_label = serializers.CharField()
    comment = serializers.CharField()
    created_at = serializers.CharField()
