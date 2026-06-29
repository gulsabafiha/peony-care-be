from rest_framework import serializers

from apps.accounts.location_settings_services import ALLOWED_BROWSE_RADIUS_KM
from apps.common.choices import LocationPlaceType


class LocationHistoryItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    place_name = serializers.CharField()
    area_label = serializers.CharField()
    place_type = serializers.CharField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    visited_at = serializers.CharField()


class ReceiverLocationSettingsSerializer(serializers.Serializer):
    browse_radius_km = serializers.FloatField()
    radius_options_km = serializers.ListField(child=serializers.FloatField())
    location_services_enabled = serializers.BooleanField()
    save_location_history = serializers.BooleanField()
    latitude = serializers.FloatField(allow_null=True)
    longitude = serializers.FloatField(allow_null=True)
    recent_places_count = serializers.IntegerField()
    recent_places = LocationHistoryItemSerializer(many=True)


class UpdateLocationSettingsSerializer(serializers.Serializer):
    browse_radius_km = serializers.FloatField(required=False)
    location_services_enabled = serializers.BooleanField(required=False)
    save_location_history = serializers.BooleanField(required=False)
    latitude = serializers.FloatField(min_value=-90, max_value=90, required=False)
    longitude = serializers.FloatField(min_value=-180, max_value=180, required=False)

    def validate_browse_radius_km(self, value):
        if value not in ALLOWED_BROWSE_RADIUS_KM:
            allowed = ", ".join(str(option) for option in ALLOWED_BROWSE_RADIUS_KM)
            raise serializers.ValidationError(f"Browse radius must be one of: {allowed} km.")
        return value


class RecordLocationVisitSerializer(serializers.Serializer):
    place_name = serializers.CharField(max_length=200)
    area_label = serializers.CharField(max_length=300)
    place_type = serializers.ChoiceField(
        choices=LocationPlaceType.choices,
        required=False,
        default=LocationPlaceType.OTHER,
    )
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)


class ClearLocationHistoryResponseSerializer(serializers.Serializer):
    cleared = serializers.BooleanField()
    recent_places_count = serializers.IntegerField()
