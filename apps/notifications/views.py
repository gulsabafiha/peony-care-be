from drf_spectacular.utils import extend_schema
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated

from apps.common.exceptions import success_response
from apps.common.permissions import IsRestaurant
from apps.common.schema import enveloped_schema
from apps.notifications import services, settings_services
from apps.notifications.serializers import (
    NotificationSettingsSerializer,
    NotificationSettingsUpdateSerializer,
    UnreadCountSerializer,
)


class UnreadCountView(GenericAPIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Notifications"],
        summary="Unread notification count",
        responses={200: enveloped_schema(UnreadCountSerializer, "UnreadCountEnvelope")},
    )
    def get(self, request):
        return success_response(services.get_unread_count(request.user))


class RestaurantNotificationSettingsView(GenericAPIView):
    permission_classes = [IsRestaurant]

    @extend_schema(
        tags=["Restaurant"],
        summary="Restaurant notification settings",
        responses={
            200: enveloped_schema(
                NotificationSettingsSerializer, "RestaurantNotificationSettingsEnvelope"
            )
        },
    )
    def get(self, request):
        return success_response(
            settings_services.get_restaurant_notification_settings(request.user)
        )

    @extend_schema(
        tags=["Restaurant"],
        summary="Update restaurant notification settings",
        request=NotificationSettingsUpdateSerializer,
        responses={
            200: enveloped_schema(
                NotificationSettingsSerializer,
                "RestaurantNotificationSettingsUpdateEnvelope",
            )
        },
    )
    def patch(self, request):
        serializer = NotificationSettingsUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = settings_services.update_restaurant_notification_settings(
            request.user,
            serializer.validated_data,
        )
        return success_response(data, message="Notification settings saved.")