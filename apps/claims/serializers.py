from __future__ import annotations

import uuid

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
    restaurant_id = serializers.UUIDField(required=False)
    restaurant_name = serializers.CharField(required=False)
    status = serializers.CharField()
    claimed_at = serializers.DateTimeField()
    pickup_window = serializers.CharField()
    has_review = serializers.BooleanField(required=False)
    can_review = serializers.BooleanField(required=False)


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


class ReviewTagSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    code = serializers.CharField()
    label = serializers.CharField()


def _split_tags_payload(tags) -> tuple[list, list]:
    """Accept codes, ids, labels, or tag objects from the FE ``tags`` field."""
    tag_ids: list = []
    tag_codes: list = []
    if tags is None:
        return tag_ids, tag_codes

    # Single comma-separated string (multipart / form clients).
    if isinstance(tags, str):
        tags = [part.strip() for part in tags.split(",") if part.strip()]

    for item in tags:
        if isinstance(item, dict):
            if item.get("id"):
                tag_ids.append(item["id"])
            elif item.get("code"):
                tag_codes.append(str(item["code"]).strip())
            elif item.get("label"):
                tag_codes.append(str(item["label"]).strip())
            continue

        value = str(item).strip()
        if not value:
            continue
        try:
            uuid.UUID(value)
            tag_ids.append(value)
        except ValueError:
            tag_codes.append(value)
    return tag_ids, tag_codes


class RestaurantReviewSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    restaurant_id = serializers.UUIDField()
    reviewer_name = serializers.CharField(allow_blank=True)
    rating = serializers.IntegerField()
    rating_label = serializers.CharField(allow_null=True)
    tag_codes = serializers.ListField(child=serializers.CharField())
    tags = ReviewTagSerializer(many=True)
    comment = serializers.CharField(allow_blank=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    message = serializers.CharField(required=False)
    success_message = serializers.CharField(required=False)


class RatingOptionSerializer(serializers.Serializer):
    value = serializers.IntegerField()
    label = serializers.CharField()


class RestaurantReviewFormSerializer(serializers.Serializer):
    restaurant_id = serializers.UUIDField()
    restaurant_name = serializers.CharField()
    latest_food_name = serializers.CharField(required=False)
    collected_at = serializers.DateTimeField(allow_null=True)
    collected_label = serializers.CharField()
    context_subtitle = serializers.CharField()
    can_review = serializers.BooleanField()
    has_review = serializers.BooleanField()
    rating = serializers.IntegerField(allow_null=True)
    rating_label = serializers.CharField(allow_null=True)
    rating_options = RatingOptionSerializer(many=True)
    tags = ReviewTagSerializer(many=True)
    review = RestaurantReviewSerializer(allow_null=True)


class CreateRestaurantReviewSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(required=False, allow_blank=True, default="")
    tag_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
    )
    tag_codes = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
    )
    # FE often posts selected chips as ``tags`` (codes, ids, labels, or objects).
    tags = serializers.JSONField(required=False)

    def validate_tags(self, value):
        if value is None:
            return value
        if isinstance(value, (list, str)):
            return value
        raise serializers.ValidationError("tags must be a list or comma-separated string.")

    def validate(self, data):
        tags = data.pop("tags", None)
        if tags is not None:
            from_ids, from_codes = _split_tags_payload(tags)
            merged_ids = list(data.get("tag_ids") or []) + from_ids
            merged_codes = list(data.get("tag_codes") or []) + from_codes
            if merged_ids:
                data["tag_ids"] = merged_ids
            if merged_codes:
                data["tag_codes"] = merged_codes
        return data


class UpdateRestaurantReviewSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=5, required=False)
    comment = serializers.CharField(required=False, allow_blank=True)
    tag_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
    )
    tag_codes = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
    )
    tags = serializers.JSONField(required=False)

    def validate_tags(self, value):
        if value is None:
            return value
        if isinstance(value, (list, str)):
            return value
        raise serializers.ValidationError("tags must be a list or comma-separated string.")

    def validate(self, data):
        tags = data.pop("tags", serializers.empty)
        if tags is not serializers.empty:
            from_ids, from_codes = _split_tags_payload(tags)
            data["tag_ids"] = list(data.get("tag_ids") or []) + from_ids
            data["tag_codes"] = list(data.get("tag_codes") or []) + from_codes

        if not data:
            raise serializers.ValidationError("Provide at least one field to update.")
        return data


class DeleteRestaurantReviewSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    restaurant_id = serializers.UUIDField()
    deleted = serializers.BooleanField()
    message = serializers.CharField()
