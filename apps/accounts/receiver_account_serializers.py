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


class DeleteAccountResponseSerializer(serializers.Serializer):
    deleted = serializers.BooleanField()
