from drf_spectacular.utils import extend_schema
from rest_framework.generics import GenericAPIView

from apps.common.exceptions import success_response
from apps.common.permissions import IsDonor
from apps.common.schema import enveloped_schema
from apps.donors import services
from apps.donors.serializers import (
    CreateMealOrderSerializer,
    CreateMoneyDonationSerializer,
    CreditPreferenceSerializer,
    DonorDashboardSerializer,
    DonorProfileSerializer,
    DonorProfileUpdateSerializer,
)


class DashboardView(GenericAPIView):
    permission_classes = [IsDonor]

    @extend_schema(
        tags=["Donor"],
        summary="Donor home impact and recent donations",
        responses={200: enveloped_schema(DonorDashboardSerializer, "DonorDashboardEnvelope")},
    )
    def get(self, request):
        return success_response(services.get_dashboard(request.user))


class HistoryView(GenericAPIView):
    permission_classes = [IsDonor]

    @extend_schema(
        tags=["Donor"],
        summary="Donation history (meals and money)",
    )
    def get(self, request):
        return success_response(services.get_history(request.user))


class ImpactView(GenericAPIView):
    permission_classes = [IsDonor]

    @extend_schema(
        tags=["Donor"],
        summary="Impact stats and monthly chart data",
    )
    def get(self, request):
        return success_response(services.get_impact(request.user))


class CreditPreferenceView(GenericAPIView):
    permission_classes = [IsDonor]

    @extend_schema(
        tags=["Donor"],
        summary="Get credit preference",
        responses={200: enveloped_schema(CreditPreferenceSerializer, "CreditPreferenceEnvelope")},
    )
    def get(self, request):
        return success_response(services.get_credit_preference(request.user))

    @extend_schema(
        tags=["Donor"],
        summary="Update credit preference",
        request=CreditPreferenceSerializer,
        responses={
            200: enveloped_schema(CreditPreferenceSerializer, "CreditPreferenceUpdateEnvelope")
        },
    )
    def patch(self, request):
        serializer = CreditPreferenceSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = services.update_credit_preference(
            request.user,
            serializer.validated_data["credit_preference"],
        )
        return success_response(data)


class DonorProfileView(GenericAPIView):
    permission_classes = [IsDonor]

    @extend_schema(
        tags=["Donor"],
        summary="Get donor profile",
        responses={200: enveloped_schema(DonorProfileSerializer, "DonorProfileEnvelope")},
    )
    def get(self, request):
        return success_response(services.get_profile_data(request.user))

    @extend_schema(
        tags=["Donor"],
        summary="Update donor profile",
        request=DonorProfileUpdateSerializer,
        responses={200: enveloped_schema(DonorProfileSerializer, "DonorProfileUpdateEnvelope")},
    )
    def patch(self, request):
        serializer = DonorProfileUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = services.update_profile_data(request.user, serializer.validated_data)
        return success_response(data)


class RestaurantBrowseView(GenericAPIView):
    permission_classes = [IsDonor]

    @extend_schema(
        tags=["Donor"],
        summary="Browse approved restaurants to sponsor",
    )
    def get(self, request):
        return success_response(services.list_restaurants())


class RestaurantMenuView(GenericAPIView):
    permission_classes = [IsDonor]

    @extend_schema(
        tags=["Donor"],
        summary="Admin-managed menu for a restaurant",
    )
    def get(self, request, restaurant_id):
        return success_response(services.get_restaurant_menu(str(restaurant_id)))


class MealOrderCreateView(GenericAPIView):
    permission_classes = [IsDonor]

    @extend_schema(
        tags=["Donor"],
        summary="Place meal order and auto-post sponsored food listing",
        request=CreateMealOrderSerializer,
    )
    def post(self, request):
        serializer = CreateMealOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = services.create_meal_order(request.user, serializer.validated_data)
        return success_response(data, status_code=201)


class MoneyDonationCreateView(GenericAPIView):
    permission_classes = [IsDonor]

    @extend_schema(
        tags=["Donor"],
        summary="Create money donation with PayNow reference",
        request=CreateMoneyDonationSerializer,
    )
    def post(self, request):
        serializer = CreateMoneyDonationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = services.create_money_donation(request.user, serializer.validated_data)
        return success_response(data, status_code=201)


class MoneyDonationConfirmTransferView(GenericAPIView):
    permission_classes = [IsDonor]

    @extend_schema(
        tags=["Donor"],
        summary="Mark PayNow transfer as sent",
    )
    def post(self, request, donation_id):
        data = services.confirm_money_transfer(request.user, str(donation_id))
        return success_response(data)
