from drf_spectacular.utils import extend_schema
from rest_framework.generics import GenericAPIView

from apps.accounts import location_settings_services
from apps.accounts.location_settings_serializers import (
    ClearLocationHistoryResponseSerializer,
    ReceiverLocationSettingsSerializer,
    RecordLocationVisitSerializer,
    UpdateLocationSettingsSerializer,
)
from apps.common.exceptions import success_response
from apps.common.permissions import IsReceiver
from apps.common.schema import enveloped_schema


class ReceiverLocationSettingsView(GenericAPIView):
    permission_classes = [IsReceiver]

    @extend_schema(
        tags=["Receiver"],
        summary="Get location settings",
        responses={
            200: enveloped_schema(
                ReceiverLocationSettingsSerializer,
                "ReceiverLocationSettingsEnvelope",
            )
        },
    )
    def get(self, request):
        data = location_settings_services.get_location_settings(request.user)
        return success_response(data)

    @extend_schema(
        tags=["Receiver"],
        summary="Update location settings",
        request=UpdateLocationSettingsSerializer,
        responses={
            200: enveloped_schema(
                ReceiverLocationSettingsSerializer,
                "ReceiverLocationSettingsUpdateEnvelope",
            )
        },
    )
    def patch(self, request):
        serializer = UpdateLocationSettingsSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = location_settings_services.update_location_settings(
            request.user,
            serializer.validated_data,
        )
        return success_response(data)


class ReceiverLocationHistoryView(GenericAPIView):
    permission_classes = [IsReceiver]
    serializer_class = RecordLocationVisitSerializer

    @extend_schema(
        tags=["Receiver"],
        summary="Record a recent place visit",
        request=RecordLocationVisitSerializer,
        responses={
            201: enveloped_schema(
                RecordLocationVisitSerializer,
                "RecordLocationVisitEnvelope",
            )
        },
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entry = location_settings_services.record_location_visit(
            request.user,
            serializer.validated_data,
        )
        if entry is None:
            return success_response({"recorded": False})
        return success_response(entry, status_code=201)

    @extend_schema(
        tags=["Receiver"],
        summary="Clear location history",
        responses={
            200: enveloped_schema(
                ClearLocationHistoryResponseSerializer,
                "ClearLocationHistoryEnvelope",
            )
        },
    )
    def delete(self, request):
        data = location_settings_services.clear_location_history(request.user)
        return success_response(data)
