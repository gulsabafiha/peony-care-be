from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated

from apps.common.exceptions import success_response
from apps.common.permissions import IsRestaurant
from apps.common.schema import enveloped_schema
from apps.notifications import services, settings_services
from apps.notifications.serializers import (
    MarkAllReadSerializer,
    NotificationItemSerializer,
    NotificationListSerializer,
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


class NotificationListView(GenericAPIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Notifications"],
        summary="List notifications grouped by date",
        parameters=[
            OpenApiParameter(
                name="unread_only",
                type=bool,
                location=OpenApiParameter.QUERY,
                required=False,
                description="If true, return only unread notifications.",
            ),
            OpenApiParameter(
                name="page",
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Page number (1-based, default 1).",
            ),
            OpenApiParameter(
                name="page_size",
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Items per page (1–100, default 20).",
            ),
        ],
        responses={200: enveloped_schema(NotificationListSerializer, "NotificationListEnvelope")},
    )
    def get(self, request):
        unread_raw = request.query_params.get("unread_only", "").lower()
        unread_only = unread_raw in {"1", "true", "yes"}
        try:
            page = int(request.query_params.get("page", 1))
        except (TypeError, ValueError):
            page = 1
        try:
            page_size = int(
                request.query_params.get("page_size", services.DEFAULT_PAGE_SIZE)
            )
        except (TypeError, ValueError):
            page_size = services.DEFAULT_PAGE_SIZE
        data = services.list_notifications(
            request.user,
            unread_only=unread_only,
            page=page,
            page_size=page_size,
        )
        return success_response(data)


class MarkNotificationReadView(GenericAPIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Notifications"],
        summary="Mark a notification as read",
        responses={200: enveloped_schema(NotificationItemSerializer, "NotificationReadEnvelope")},
    )
    def post(self, request, notification_id):
        data = services.mark_notification_read(request.user, str(notification_id))
        return success_response(data, message="Notification marked as read.")


class MarkAllNotificationsReadView(GenericAPIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Notifications"],
        summary="Mark all notifications as read",
        responses={200: enveloped_schema(MarkAllReadSerializer, "NotificationMarkAllReadEnvelope")},
    )
    def post(self, request):
        data = services.mark_all_notifications_read(request.user)
        return success_response(data, message="All notifications marked as read.")


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
