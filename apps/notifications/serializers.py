from rest_framework import serializers


class UnreadCountSerializer(serializers.Serializer):
    unread_count = serializers.IntegerField()


class NotificationItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    type = serializers.CharField()
    title = serializers.CharField()
    body = serializers.CharField()
    payload = serializers.DictField()
    is_read = serializers.BooleanField()
    read_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()


class NotificationGroupSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    date = serializers.CharField()
    count = serializers.IntegerField()
    items = NotificationItemSerializer(many=True)


class NotificationPaginationSerializer(serializers.Serializer):
    page = serializers.IntegerField()
    page_size = serializers.IntegerField()
    total_count = serializers.IntegerField()
    total_pages = serializers.IntegerField()
    has_next = serializers.BooleanField()
    has_previous = serializers.BooleanField()


class NotificationListSerializer(serializers.Serializer):
    groups = NotificationGroupSerializer(many=True)
    unread_count = serializers.IntegerField()
    pagination = NotificationPaginationSerializer()


class MarkAllReadSerializer(serializers.Serializer):
    marked_read = serializers.IntegerField()
    unread_count = serializers.IntegerField()


class NotificationSettingsSerializer(serializers.Serializer):
    push_enabled = serializers.BooleanField()
    email_enabled = serializers.BooleanField()
    alert_new_claim = serializers.BooleanField()
    alert_sponsored = serializers.BooleanField()
    alert_all_claimed = serializers.BooleanField()
    alert_window_expiring = serializers.BooleanField()
    alert_no_show = serializers.BooleanField()
    alert_donation_claimed = serializers.BooleanField()
    alert_receipts = serializers.BooleanField()
    updated_at = serializers.DateTimeField()


class NotificationSettingsUpdateSerializer(serializers.Serializer):
    push_enabled = serializers.BooleanField(required=False)
    email_enabled = serializers.BooleanField(required=False)
    alert_new_claim = serializers.BooleanField(required=False)
    alert_sponsored = serializers.BooleanField(required=False)
    alert_all_claimed = serializers.BooleanField(required=False)
    alert_window_expiring = serializers.BooleanField(required=False)
    alert_no_show = serializers.BooleanField(required=False)
    alert_donation_claimed = serializers.BooleanField(required=False)
    alert_receipts = serializers.BooleanField(required=False)
