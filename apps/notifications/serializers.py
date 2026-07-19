from rest_framework import serializers


class UnreadCountSerializer(serializers.Serializer):
    unread_count = serializers.IntegerField()
