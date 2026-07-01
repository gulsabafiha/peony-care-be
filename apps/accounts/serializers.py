from rest_framework import serializers

from apps.common.choices import OtpPurpose


class OtpSendSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    purpose = serializers.ChoiceField(choices=OtpPurpose.choices)


class OtpVerifySerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    code = serializers.CharField(min_length=4, max_length=4)


class ReceiverRegisterSerializer(serializers.Serializer):
    display_name = serializers.CharField(max_length=100)
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)


class RestaurantRegisterSerializer(serializers.Serializer):
    restaurant_name = serializers.CharField(max_length=200)
    uen = serializers.CharField(max_length=20)
    address = serializers.CharField()
    contact_name = serializers.CharField(max_length=100)
    contact_email = serializers.EmailField(required=False, allow_blank=True)
    contact_phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    latitude = serializers.FloatField(min_value=-90, max_value=90, required=False)
    longitude = serializers.FloatField(min_value=-180, max_value=180, required=False)

    def validate(self, data):
        lat = data.get("latitude")
        lng = data.get("longitude")
        if (lat is None) != (lng is None):
            raise serializers.ValidationError(
                {"latitude": "latitude and longitude must be provided together."}
            )
        return data


class DonorRegisterSerializer(serializers.Serializer):
    display_name = serializers.CharField(max_length=100)
    contact_email = serializers.EmailField(required=False, allow_blank=True)


class RefreshTokenSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class UserSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    phone = serializers.CharField()
    role = serializers.CharField()
    is_active = serializers.BooleanField()


class AuthTokensSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserSummarySerializer(required=False)


class OtpSendResponseSerializer(serializers.Serializer):
    phone = serializers.CharField()
    purpose = serializers.CharField()
    expires_at = serializers.DateTimeField()
    message = serializers.CharField()


class OtpVerifyRegistrationResponseSerializer(serializers.Serializer):
    registration_token = serializers.CharField()
    phone = serializers.CharField()
    message = serializers.CharField()


class MessageResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
