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
    opening_hours = serializers.CharField(allow_blank=True)
    opens_at = serializers.TimeField(allow_null=True)
    closes_at = serializers.TimeField(allow_null=True)
    distance_km = serializers.FloatField()
    active_meal_count = serializers.IntegerField()


class RestaurantMealSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    title = serializers.CharField(required=False)
    subtitle = serializers.CharField(required=False)
    description = serializers.CharField()
    category = serializers.CharField()
    photo_url = serializers.CharField(allow_null=True)
    quantity_available = serializers.IntegerField()
    quantity_original = serializers.IntegerField(required=False)
    quantity_left_label = serializers.CharField(required=False)
    unit = serializers.CharField(required=False)
    pickup_start = serializers.CharField()
    pickup_end = serializers.CharField()
    pickup_window = serializers.CharField()
    sponsorship_type = serializers.CharField()
    is_sponsored = serializers.BooleanField(required=False)
    sponsor_display_name = serializers.CharField(allow_null=True)
    sponsor_initials = serializers.CharField(allow_null=True, required=False)


class RestaurantDetailImpactSerializer(serializers.Serializer):
    people_fed = serializers.IntegerField()
    people_fed_label = serializers.CharField()
    donations_count = serializers.IntegerField()
    donations_label = serializers.CharField()
    claim_rate_pct = serializers.IntegerField(allow_null=True)
    claim_rate_display = serializers.CharField()
    claim_rate_label = serializers.CharField()


class ReceiverRestaurantDetailSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    address = serializers.CharField()
    postal_code = serializers.CharField()
    area_label = serializers.CharField(allow_null=True, required=False)
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    photo_url = serializers.CharField(allow_null=True)
    about = serializers.CharField()
    opening_hours = serializers.CharField()
    contact_phone = serializers.CharField()
    is_verified = serializers.BooleanField()
    verified_label = serializers.CharField(allow_null=True, required=False)
    distance_km = serializers.FloatField()
    active_meal_count = serializers.IntegerField()
    available_now_label = serializers.CharField(required=False)
    categories = serializers.ListField(child=serializers.CharField())
    available_meals = RestaurantMealSummarySerializer(many=True)
    impact = RestaurantDetailImpactSerializer(required=False)
    people_fed = serializers.IntegerField(required=False)
    donations_count = serializers.IntegerField(required=False)
    claim_rate_pct = serializers.IntegerField(allow_null=True, required=False)
    claim_rate_display = serializers.CharField(required=False)
    rating = serializers.FloatField(allow_null=True, required=False)
    rating_display = serializers.CharField(required=False)
    review_count = serializers.IntegerField(required=False)
    reviews_available = serializers.BooleanField(required=False)


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
