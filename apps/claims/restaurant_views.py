from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.generics import GenericAPIView

from apps.claims import report_services, restaurant_services
from apps.claims.serializers import (
    ClaimReportContextSerializer,
    ClaimReportSerializer,
    RestaurantClaimBoardSerializer,
    RestaurantClaimSerializer,
    SubmitClaimReportSerializer,
)
from apps.common.exceptions import success_response
from apps.common.permissions import IsRestaurant
from apps.common.schema import enveloped_schema


class TodayClaimsBoardView(GenericAPIView):
    permission_classes = [IsRestaurant]

    @extend_schema(
        tags=["Restaurant"],
        summary="Today's claims board",
        parameters=[
            OpenApiParameter(
                "status",
                str,
                OpenApiParameter.QUERY,
                enum=["all", "pending", "collected", "no_show"],
            )
        ],
        responses={
            200: enveloped_schema(RestaurantClaimBoardSerializer, "TodayClaimsEnvelope")
        },
    )
    def get(self, request):
        status = request.query_params.get("status", "all")
        return success_response(
            restaurant_services.get_today_claims(request.user, status=status)
        )


class DonationClaimsView(GenericAPIView):
    permission_classes = [IsRestaurant]

    @extend_schema(
        tags=["Restaurant"],
        summary="Claims for a donation",
        responses={
            200: enveloped_schema(RestaurantClaimSerializer, "DonationClaimsEnvelope", many=True)
        },
    )
    def get(self, request, food_id):
        return success_response(
            restaurant_services.list_donation_claims(request.user, str(food_id))
        )


class MarkClaimCollectedView(GenericAPIView):
    permission_classes = [IsRestaurant]

    @extend_schema(
        tags=["Restaurant"],
        summary="Mark a claim as collected",
        request=None,
        responses={
            200: enveloped_schema(RestaurantClaimSerializer, "MarkClaimCollectedEnvelope")
        },
    )
    def post(self, request, claim_id):
        return success_response(
            restaurant_services.mark_claim_collected(request.user, str(claim_id))
        )


class MarkClaimNoShowView(GenericAPIView):
    permission_classes = [IsRestaurant]

    @extend_schema(
        tags=["Restaurant"],
        summary="Mark a claim as no-show",
        request=None,
        responses={200: enveloped_schema(RestaurantClaimSerializer, "MarkClaimNoShowEnvelope")},
    )
    def post(self, request, claim_id):
        return success_response(
            restaurant_services.mark_claim_no_show(request.user, str(claim_id))
        )


class UndoClaimNoShowView(GenericAPIView):
    permission_classes = [IsRestaurant]

    @extend_schema(
        tags=["Restaurant"],
        summary="Undo a no-show claim (back to pending)",
        request=None,
        responses={200: enveloped_schema(RestaurantClaimSerializer, "UndoClaimNoShowEnvelope")},
    )
    def post(self, request, claim_id):
        return success_response(
            restaurant_services.undo_claim_no_show(request.user, str(claim_id))
        )


class ClaimReportView(GenericAPIView):
    permission_classes = [IsRestaurant]

    @extend_schema(
        tags=["Restaurant"],
        summary="Report form context and reasons for a claim",
        responses={
            200: enveloped_schema(ClaimReportContextSerializer, "ClaimReportContextEnvelope")
        },
    )
    def get(self, request, claim_id):
        return success_response(
            report_services.get_claim_report_context(request.user, str(claim_id))
        )

    @extend_schema(
        tags=["Restaurant"],
        summary="Submit a confidential claim report",
        request=SubmitClaimReportSerializer,
        responses={201: enveloped_schema(ClaimReportSerializer, "ClaimReportSubmitEnvelope")},
    )
    def post(self, request, claim_id):
        serializer = SubmitClaimReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = report_services.submit_claim_report(
            request.user,
            str(claim_id),
            reason_id=(
                str(serializer.validated_data["reason_id"])
                if serializer.validated_data.get("reason_id")
                else None
            ),
            reason_code=serializer.validated_data.get("reason_code"),
            comment=serializer.validated_data.get("comment", ""),
        )
        return success_response(data, status_code=201)
