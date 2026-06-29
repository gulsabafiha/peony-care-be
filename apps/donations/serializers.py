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
