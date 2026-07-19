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
    restaurant_name = serializers.CharField(required=False)
    status = serializers.CharField()
    claimed_at = serializers.DateTimeField()
    pickup_window = serializers.CharField()


class RestaurantClaimSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    receiver_name = serializers.CharField()
    receiver_initials = serializers.CharField(required=False)
    food_id = serializers.UUIDField(required=False)
    food_name = serializers.CharField()
    items_label = serializers.CharField(required=False)
    claimed_at = serializers.DateTimeField()
    collected_at = serializers.DateTimeField(allow_null=True)
    collected_at_label = serializers.CharField(allow_null=True, required=False)
    no_show_at = serializers.DateTimeField(allow_null=True, required=False)
    window_expired_label = serializers.CharField(allow_null=True, required=False)
    pickup_window = serializers.CharField()
    pickup_window_short = serializers.CharField(required=False)
    status = serializers.CharField()
    status_key = serializers.CharField(required=False)
    status_label = serializers.CharField()
    can_mark_collected = serializers.BooleanField()
    can_mark_no_show = serializers.BooleanField(required=False)
    can_undo_no_show = serializers.BooleanField(required=False)


class RestaurantClaimSummarySerializer(serializers.Serializer):
    pending = serializers.IntegerField()
    collected = serializers.IntegerField()
    no_show = serializers.IntegerField()
    label = serializers.CharField()


class RestaurantClaimTabSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    count = serializers.IntegerField()


class RestaurantClaimGroupSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    claims = RestaurantClaimSerializer(many=True)


class RestaurantClaimBoardSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    summary = RestaurantClaimSummarySerializer()
    tabs = RestaurantClaimTabSerializer(many=True)
    selected_status = serializers.CharField()
    groups = RestaurantClaimGroupSerializer(many=True)
    claims = RestaurantClaimSerializer(many=True)
    hint = serializers.CharField()


class ClaimReportReasonSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    code = serializers.CharField()
    label = serializers.CharField()


class ClaimReportContextSerializer(serializers.Serializer):
    claim_id = serializers.UUIDField()
    receiver_name = serializers.CharField()
    receiver_phone_tail = serializers.CharField()
    food_name = serializers.CharField()
    pickup_window_short = serializers.CharField()
    context_line = serializers.CharField()
    footer_note = serializers.CharField()
    reasons = ClaimReportReasonSerializer(many=True)


class SubmitClaimReportSerializer(serializers.Serializer):
    reason_id = serializers.UUIDField(required=False)
    reason_code = serializers.CharField(required=False)
    comment = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, data):
        if not data.get("reason_id") and not data.get("reason_code"):
            raise serializers.ValidationError(
                {"reason_id": "Provide reason_id or reason_code."}
            )
        return data


class ClaimReportSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    claim_id = serializers.UUIDField()
    receiver_name = serializers.CharField()
    reason_id = serializers.UUIDField()
    reason_code = serializers.CharField()
    reason_label = serializers.CharField()
    comment = serializers.CharField(allow_blank=True)
    created_at = serializers.DateTimeField()
    message = serializers.CharField()
