from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.generics import GenericAPIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

from apps.common.exceptions import success_response
from apps.common.permissions import IsRestaurant
from apps.common.schema import enveloped_schema
from apps.donations import (
    analytics_services,
    location_services,
    menu_photo_services,
    restaurant_services,
)
from apps.donations.restaurant_serializers import (
    AnalyticsRangeQuerySerializer,
    AnalyticsSerializer,
    ApprovalStatusSerializer,
    CreateDonationSerializer,
    DashboardSerializer,
    DonationListQuerySerializer,
    DonationListResponseSerializer,
    LocationConfirmSerializer,
    LocationResultSerializer,
    LocationReverseQuerySerializer,
    LocationSearchQuerySerializer,
    LocationSearchResponseSerializer,
    MenuPhotoListSerializer,
    MenuPhotoReorderSerializer,
    MenuPhotoUploadSerializer,
    RestaurantDonationSerializer,
    RestaurantProfileSerializer,
    RestaurantProfileUpdateSerializer,
    UpdateDonationSerializer,
)


class DashboardView(GenericAPIView):
    permission_classes = [IsRestaurant]

    @extend_schema(
        tags=["Restaurant"],
        summary="Restaurant home dashboard",
        responses={200: enveloped_schema(DashboardSerializer, "RestaurantDashboardEnvelope")},
    )
    def get(self, request):
        return success_response(restaurant_services.get_dashboard(request.user))


class AnalyticsView(GenericAPIView):
    permission_classes = [IsRestaurant]

    @extend_schema(
        tags=["Restaurant"],
        summary="Restaurant analytics / impact",
        parameters=[
            OpenApiParameter(
                "range",
                str,
                OpenApiParameter.QUERY,
                enum=["7D", "30D", "3M", "1Y", "ALL"],
            )
        ],
        responses={200: enveloped_schema(AnalyticsSerializer, "RestaurantAnalyticsEnvelope")},
    )
    def get(self, request):
        serializer = AnalyticsRangeQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        return success_response(
            analytics_services.get_restaurant_analytics(
                request.user,
                range_key=serializer.validated_data.get("range", "30D"),
            )
        )


class DonationListCreateView(GenericAPIView):
    permission_classes = [IsRestaurant]
    serializer_class = CreateDonationSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(
        tags=["Restaurant"],
        operation_id="v1_restaurant_donations_list",
        summary="List donations by status with tab counts and date groups",
        parameters=[
            OpenApiParameter(
                "status",
                str,
                OpenApiParameter.QUERY,
                enum=["active", "past", "inactive"],
            )
        ],
        responses={
            200: enveloped_schema(DonationListResponseSerializer, "DonationListEnvelope")
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
        request={
            "multipart/form-data": CreateDonationSerializer,
            "application/json": CreateDonationSerializer,
        },
        responses={201: enveloped_schema(RestaurantDonationSerializer, "CreateDonationEnvelope")},
    )
    def post(self, request):
        serializer = CreateDonationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = restaurant_services.create_donation(
            request.user,
            serializer.validated_data,
            request=request,
        )
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
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(
        tags=["Restaurant"],
        summary="Restaurant profile",
        responses={200: enveloped_schema(RestaurantProfileSerializer, "RestaurantProfileEnvelope")},
    )
    def get(self, request):
        return success_response(
            restaurant_services.get_restaurant_profile_data(request.user, request=request)
        )

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
            request=request,
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


class LocationSearchView(GenericAPIView):
    permission_classes = [IsRestaurant]

    @extend_schema(
        tags=["Restaurant"],
        summary="Search address or postal code",
        parameters=[OpenApiParameter("q", str, OpenApiParameter.QUERY, required=True)],
        responses={
            200: enveloped_schema(LocationSearchResponseSerializer, "LocationSearchEnvelope")
        },
    )
    def get(self, request):
        serializer = LocationSearchQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        return success_response(
            location_services.search_restaurant_locations(serializer.validated_data["q"])
        )


class LocationReverseView(GenericAPIView):
    permission_classes = [IsRestaurant]

    @extend_schema(
        tags=["Restaurant"],
        summary="Reverse geocode a map pin",
        parameters=[
            OpenApiParameter("lat", float, OpenApiParameter.QUERY, required=True),
            OpenApiParameter("lng", float, OpenApiParameter.QUERY, required=True),
        ],
        responses={200: enveloped_schema(LocationResultSerializer, "LocationReverseEnvelope")},
    )
    def get(self, request):
        serializer = LocationReverseQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        return success_response(
            location_services.reverse_restaurant_location(
                serializer.validated_data["lat"],
                serializer.validated_data["lng"],
            )
        )


class LocationConfirmView(GenericAPIView):
    permission_classes = [IsRestaurant]

    @extend_schema(
        tags=["Restaurant"],
        summary="Confirm and save restaurant location",
        request=LocationConfirmSerializer,
        responses={200: enveloped_schema(LocationResultSerializer, "LocationConfirmEnvelope")},
    )
    def post(self, request):
        serializer = LocationConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return success_response(
            location_services.confirm_restaurant_location(
                request.user,
                serializer.validated_data,
                request=request,
            )
        )


class MenuPhotoListCreateView(GenericAPIView):
    permission_classes = [IsRestaurant]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(
        tags=["Restaurant"],
        summary="List menu photos",
        responses={200: enveloped_schema(MenuPhotoListSerializer, "MenuPhotoListEnvelope")},
    )
    def get(self, request):
        return success_response(
            menu_photo_services.list_menu_photos(request.user, request=request)
        )

    @extend_schema(
        tags=["Restaurant"],
        summary="Upload menu photos (max 10)",
        request={"multipart/form-data": MenuPhotoUploadSerializer},
        responses={201: enveloped_schema(MenuPhotoListSerializer, "MenuPhotoCreateEnvelope")},
    )
    def post(self, request):
        # Multipart clients may send repeated `photos` keys; merge with optional `photo`.
        payload = request.data
        multi_photos = request.FILES.getlist("photos")
        if multi_photos:
            payload = request.data.copy()
            payload.setlist("photos", multi_photos)
        serializer = MenuPhotoUploadSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        data = menu_photo_services.create_menu_photos(
            request.user,
            serializer.validated_data["files"],
            request=request,
        )
        return success_response(data, status_code=201)


class MenuPhotoDetailView(GenericAPIView):
    permission_classes = [IsRestaurant]

    @extend_schema(
        tags=["Restaurant"],
        summary="Delete a menu photo",
        responses={200: enveloped_schema(MenuPhotoListSerializer, "MenuPhotoDeleteEnvelope")},
    )
    def delete(self, request, photo_id):
        return success_response(
            menu_photo_services.delete_menu_photo(
                request.user,
                str(photo_id),
                request=request,
            )
        )


class MenuPhotoReorderView(GenericAPIView):
    permission_classes = [IsRestaurant]

    @extend_schema(
        tags=["Restaurant"],
        summary="Reorder menu photos",
        request=MenuPhotoReorderSerializer,
        responses={200: enveloped_schema(MenuPhotoListSerializer, "MenuPhotoReorderEnvelope")},
    )
    def patch(self, request):
        serializer = MenuPhotoReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        photo_ids = [str(photo_id) for photo_id in serializer.validated_data["photo_ids"]]
        return success_response(
            menu_photo_services.reorder_menu_photos(
                request.user,
                photo_ids,
                request=request,
            )
        )
