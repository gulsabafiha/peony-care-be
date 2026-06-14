from rest_framework import serializers


class ReceiverProfileSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    display_name = serializers.CharField()
    phone = serializers.CharField()
    total_claims = serializers.IntegerField()
    last_claim_date = serializers.CharField(allow_null=True)
    stats = serializers.DictField()


class ReceiverProfileUpdateSerializer(serializers.Serializer):
    display_name = serializers.CharField(max_length=100)


class ReceiverStatsSerializer(serializers.Serializer):
    lifetime_meals = serializers.IntegerField()
    restaurants_count = serializers.IntegerField()
