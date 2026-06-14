from drf_spectacular.utils import extend_schema
from rest_framework.generics import GenericAPIView

from apps.accounts import receiver_services
from apps.accounts.receiver_serializers import (
    ReceiverProfileSerializer,
    ReceiverProfileUpdateSerializer,
    ReceiverStatsSerializer,
)
from apps.common.exceptions import success_response
from apps.common.permissions import IsReceiver
from apps.common.schema import enveloped_schema


class ReceiverProfileView(GenericAPIView):
    permission_classes = [IsReceiver]

    @extend_schema(
        tags=["Receiver"],
        summary="Get receiver profile",
        responses={200: enveloped_schema(ReceiverProfileSerializer, "ReceiverProfileEnvelope")},
    )
    def get(self, request):
        data = receiver_services.get_receiver_profile(request.user)
        return success_response(data)

    @extend_schema(
        tags=["Receiver"],
        summary="Update receiver profile",
        request=ReceiverProfileUpdateSerializer,
        responses={
            200: enveloped_schema(
                ReceiverProfileSerializer,
                "ReceiverProfileUpdateEnvelope",
            )
        },
    )
    def patch(self, request):
        serializer = ReceiverProfileUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = receiver_services.update_receiver_profile(
            request.user,
            display_name=serializer.validated_data["display_name"],
        )
        return success_response(data)


class ReceiverStatsView(GenericAPIView):
    permission_classes = [IsReceiver]

    @extend_schema(
        tags=["Receiver"],
        summary="Receiver lifetime stats",
        responses={200: enveloped_schema(ReceiverStatsSerializer, "ReceiverStatsEnvelope")},
    )
    def get(self, request):
        from apps.claims.services import get_receiver_stats

        data = get_receiver_stats(request.user)
        return success_response(data)
