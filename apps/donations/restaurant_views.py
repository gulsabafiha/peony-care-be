from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.generics import GenericAPIView

from apps.common.exceptions import success_response
from apps.common.permissions import IsRestaurant
from apps.common.schema import enveloped_schema
from apps.donations import restaurant_services
from apps.donations.restaurant_serializers import (
    ApprovalStatusSerializer,
    CreateDonationSerializer,
    DashboardSerializer,
    DonationListQuerySerializer,
    RestaurantDonationSerializer,
    RestaurantProfileSerializer,
    RestaurantProfileUpdateSerializer,
    UpdateDonationSerializer,
)


class DashboardView(GenericAPIView):
    permission_classes = [IsRestaurant]

    @extend_schema(
        tags=["Restaurant"],
        summary="Dashboard home counts",
        responses={200: enveloped_schema(DashboardSerializer, "RestaurantDashboardEnvelope")},
    )
    def get(self, request):
        return success_response(restaurant_services.get_dashboard(request.user))


class DonationListCreateView(GenericAPIView):
    permission_classes = [IsRestaurant]
    serializer_class = CreateDonationSerializer

    @extend_schema(
        tags=["Restaurant"],
        operation_id="v1_restaurant_donations_list",
        summary="List donations by status",
        parameters=[
            OpenApiParameter(
                "status",
                str,
                OpenApiParameter.QUERY,
                enum=["active", "past", "inactive"],
            )
        ],
        responses={
            200: enveloped_schema(RestaurantDonationSerializer, "DonationListEnvelope", many=True)
        },
    )
    def get(self, request):
        serializer = DonationListQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = restaurant_services.list_donations(
            request.user,
            status=serializer.validated_data["status"],
        )
        return success_response(data)

    @extend_schema(
        tags=["Restaurant"],
        summary="Post new donation",
        request=CreateDonationSerializer,
        responses={201: enveloped_schema(RestaurantDonationSerializer, "CreateDonationEnvelope")},
    )
    def post(self, request):
        serializer = CreateDonationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = restaurant_services.create_donation(request.user, serializer.validated_data)
        return success_response(data, status_code=201)


class DonationDetailView(GenericAPIView):
    permission_classes = [IsRestaurant]
    serializer_class = UpdateDonationSerializer

    @extend_schema(
        tags=["Restaurant"],
        operation_id="v1_restaurant_donations_retrieve",
        summary="Donation detail with claims",
        responses={200: enveloped_schema(RestaurantDonationSerializer, "DonationDetailEnvelope")},
    )
    def get(self, request, food_id):
        data = restaurant_services.get_donation(request.user, str(food_id))
        return success_response(data)

    @extend_schema(
        tags=["Restaurant"],
        summary="Edit donation (no claims yet)",
        request=UpdateDonationSerializer,
        responses={200: enveloped_schema(RestaurantDonationSerializer, "UpdateDonationEnvelope")},
    )
    def patch(self, request, food_id):
        serializer = UpdateDonationSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = restaurant_services.update_donation(
            request.user,
            str(food_id),
            serializer.validated_data,
        )
        return success_response(data)

    @extend_schema(
        tags=["Restaurant"],
        summary="Delete inactive donation",
        responses={200: enveloped_schema(RestaurantDonationSerializer, "DeleteDonationEnvelope")},
    )
    def delete(self, request, food_id):
        data = restaurant_services.delete_donation(request.user, str(food_id))
        return success_response(data)


class DonationCloseView(GenericAPIView):
    permission_classes = [IsRestaurant]
    serializer_class = RestaurantDonationSerializer

    @extend_schema(
        tags=["Restaurant"],
        summary="Close donation early",
        request=OpenApiTypes.NONE,
        responses={200: enveloped_schema(RestaurantDonationSerializer, "CloseDonationEnvelope")},
    )
    def post(self, request, food_id):
        data = restaurant_services.close_donation(request.user, str(food_id))
        return success_response(data)


class DonationReactivateView(GenericAPIView):
    permission_classes = [IsRestaurant]
    serializer_class = RestaurantDonationSerializer

    @extend_schema(
        tags=["Restaurant"],
        summary="Reactivate inactive donation",
        request=OpenApiTypes.NONE,
        responses={
            200: enveloped_schema(RestaurantDonationSerializer, "ReactivateDonationEnvelope")
        },
    )
    def post(self, request, food_id):
        data = restaurant_services.reactivate_donation(request.user, str(food_id))
        return success_response(data)


class ApprovalStatusView(GenericAPIView):
    permission_classes = [IsRestaurant]

    @extend_schema(
        tags=["Restaurant"],
        summary="Restaurant activation status",
        responses={200: enveloped_schema(ApprovalStatusSerializer, "ApprovalStatusEnvelope")},
    )
    def get(self, request):
        return success_response(restaurant_services.get_approval_status(request.user))


class RestaurantProfileView(GenericAPIView):
    permission_classes = [IsRestaurant]

    @extend_schema(
        tags=["Restaurant"],
        summary="Restaurant profile",
        responses={200: enveloped_schema(RestaurantProfileSerializer, "RestaurantProfileEnvelope")},
    )
    def get(self, request):
        return success_response(restaurant_services.get_restaurant_profile_data(request.user))

    @extend_schema(
        tags=["Restaurant"],
        summary="Edit restaurant profile",
        request=RestaurantProfileUpdateSerializer,
        responses={
            200: enveloped_schema(RestaurantProfileSerializer, "RestaurantProfileUpdateEnvelope")
        },
    )
    def patch(self, request):
        serializer = RestaurantProfileUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = restaurant_services.update_restaurant_profile_data(
            request.user,
            serializer.validated_data,
        )
        return success_response(data)


class PublicRestaurantView(GenericAPIView):
    permission_classes = []

    @extend_schema(
        tags=["Restaurant"],
        summary="Public restaurant page",
        responses={200: enveloped_schema(RestaurantProfileSerializer, "PublicRestaurantEnvelope")},
    )
    def get(self, request, restaurant_id):
        data = restaurant_services.get_public_restaurant(str(restaurant_id))
        return success_response(data)
