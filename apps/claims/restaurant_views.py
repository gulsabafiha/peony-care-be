from drf_spectacular.utils import extend_schema
from rest_framework.generics import GenericAPIView

from apps.claims import restaurant_services
from apps.claims.serializers import ClaimHistoryItemSerializer
from apps.common.exceptions import success_response
from apps.common.permissions import IsRestaurant
from apps.common.schema import enveloped_schema


class TodayClaimsBoardView(GenericAPIView):
    permission_classes = [IsRestaurant]

    @extend_schema(
        tags=["Restaurant"],
        summary="Today's claims board",
        responses={
            200: enveloped_schema(ClaimHistoryItemSerializer, "TodayClaimsEnvelope", many=True)
        },
    )
    def get(self, request):
        return success_response(restaurant_services.get_today_claims(request.user))


class DonationClaimsView(GenericAPIView):
    permission_classes = [IsRestaurant]

    @extend_schema(
        tags=["Restaurant"],
        summary="Read-only claims for a donation",
        responses={
            200: enveloped_schema(ClaimHistoryItemSerializer, "DonationClaimsEnvelope", many=True)
        },
    )
    def get(self, request, food_id):
        return success_response(
            restaurant_services.list_donation_claims(request.user, str(food_id))
        )
