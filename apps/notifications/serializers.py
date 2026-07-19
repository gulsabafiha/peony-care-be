from rest_framework import serializers


class UnreadCountSerializer(serializers.Serializer):
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
