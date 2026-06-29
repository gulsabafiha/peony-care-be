from rest_framework import serializers


class ReceiverProfileSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    display_name = serializers.CharField()
    phone = serializers.CharField()
    latitude = serializers.FloatField(allow_null=True)
    longitude = serializers.FloatField(allow_null=True)
    browse_radius_km = serializers.FloatField()
    total_claims = serializers.IntegerField()
    last_claim_date = serializers.CharField(allow_null=True)
    stats = serializers.DictField()


class ReceiverProfileUpdateSerializer(serializers.Serializer):
    display_name = serializers.CharField(max_length=100, required=False)
    latitude = serializers.FloatField(min_value=-90, max_value=90, required=False)
    longitude = serializers.FloatField(min_value=-180, max_value=180, required=False)
    browse_radius_km = serializers.FloatField(
        min_value=0.1,
        max_value=50,
        required=False,
    )


class ReceiverStatsSerializer(serializers.Serializer):
    lifetime_meals = serializers.IntegerField()
    restaurants_count = serializers.IntegerField()
