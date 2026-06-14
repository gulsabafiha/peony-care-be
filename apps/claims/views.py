from drf_spectacular.utils import extend_schema
from rest_framework.generics import GenericAPIView

from apps.claims import services
from apps.claims.serializers import (
    ClaimHistoryItemSerializer,
    ClaimResponseSerializer,
    CreateClaimSerializer,
    DailyLimitSerializer,
)
from apps.common.exceptions import success_response
from apps.common.permissions import IsReceiver
from apps.common.schema import enveloped_schema


class TodayClaimStatusView(GenericAPIView):
    permission_classes = [IsReceiver]

    @extend_schema(
        tags=["Receiver"],
        summary="Daily claim limit status",
        responses={200: enveloped_schema(DailyLimitSerializer, "TodayClaimStatusEnvelope")},
    )
    def get(self, request):
        data = services.get_daily_limit_status(request.user)
        return success_response(data)


class ClaimsView(GenericAPIView):
    permission_classes = [IsReceiver]
    serializer_class = CreateClaimSerializer

    @extend_schema(
        tags=["Receiver"],
        summary="Claim history",
        responses={
            200: enveloped_schema(ClaimHistoryItemSerializer, "ClaimHistoryEnvelope", many=True)
        },
    )
    def get(self, request):
        data = services.list_claim_history(request.user)
        return success_response(data)

    @extend_schema(
        tags=["Receiver"],
        summary="Create claim (instant CLAIMED)",
        request=CreateClaimSerializer,
        responses={201: enveloped_schema(ClaimResponseSerializer, "CreateClaimEnvelope")},
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = services.create_claim(receiver=request.user, **serializer.validated_data)
        return success_response(data, status_code=201)


class ClaimDetailView(GenericAPIView):
    permission_classes = [IsReceiver]

    @extend_schema(
        tags=["Receiver"],
        summary="Single claim detail",
        responses={200: enveloped_schema(ClaimResponseSerializer, "ClaimDetailEnvelope")},
    )
    def get(self, request, claim_id):
        data = services.get_claim_detail(request.user, str(claim_id))
        return success_response(data)
