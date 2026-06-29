from rest_framework import serializers


class CreateClaimSerializer(serializers.Serializer):
    food_id = serializers.UUIDField()
    qr_payload = serializers.CharField(max_length=200)
    lat = serializers.FloatField()
    lng = serializers.FloatField()


class DailyLimitSerializer(serializers.Serializer):
    used = serializers.IntegerField()
    limit = serializers.IntegerField()
    can_claim = serializers.BooleanField()
    resets_at = serializers.DateTimeField()
    seconds_until_reset = serializers.IntegerField()


class ClaimResponseSerializer(serializers.Serializer):
    claim_id = serializers.UUIDField()
    status = serializers.CharField()
    food_name = serializers.CharField()
    restaurant_name = serializers.CharField()
    pickup_address = serializers.CharField()
    distance_km = serializers.FloatField()
    pickup_window = serializers.CharField()
    claimed_at = serializers.DateTimeField()
    message = serializers.CharField()
    daily_limit = DailyLimitSerializer()


class ClaimHistoryItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    food_name = serializers.CharField()
    restaurant_name = serializers.CharField()
    status = serializers.CharField()
    claimed_at = serializers.DateTimeField()
    pickup_window = serializers.CharField()
