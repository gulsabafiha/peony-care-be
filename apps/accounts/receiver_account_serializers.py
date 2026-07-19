from rest_framework import serializers


class DeleteAccountSerializer(serializers.Serializer):
    confirmation = serializers.CharField()


class DataExportResponseSerializer(serializers.Serializer):
    request_id = serializers.UUIDField()
    phone_e164 = serializers.CharField()
    status = serializers.CharField()
    requested_at = serializers.CharField()
    download_url = serializers.CharField()
    format = serializers.CharField()
    email = serializers.EmailField(allow_null=True, required=False)
    delivery = serializers.CharField(required=False)
    email_sent = serializers.BooleanField(required=False)
    eta_hours = serializers.IntegerField(required=False)
    message = serializers.CharField(required=False)
    includes = serializers.ListField(child=serializers.CharField(), required=False)


class DeleteAccountRetentionSerializer(serializers.Serializer):
    uen_contact_days = serializers.IntegerField()
    uen_contact_retained_until = serializers.CharField()
    payout_years = serializers.IntegerField()
    payout_records_retained = serializers.IntegerField()
    payout_retained_until = serializers.CharField()
    summary = serializers.ListField(child=serializers.CharField())


class DeleteAccountResponseSerializer(serializers.Serializer):
    deleted = serializers.BooleanField()
    active_donations_deactivated = serializers.IntegerField(required=False)
    retention = DeleteAccountRetentionSerializer(required=False)
