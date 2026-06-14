from rest_framework import serializers

from apps.common.choices import FoodCategory


class LocationQuerySerializer(serializers.Serializer):
    lat = serializers.FloatField()
    lng = serializers.FloatField()
    radius_km = serializers.FloatField(required=False, min_value=0.1, max_value=50)


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
