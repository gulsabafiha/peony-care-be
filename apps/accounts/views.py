from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.accounts import services
from apps.accounts.serializers import (
    AuthTokensSerializer,
    DonorRegisterSerializer,
    LogoutSerializer,
    MessageResponseSerializer,
    OtpSendResponseSerializer,
    OtpSendSerializer,
    OtpVerifyRegistrationResponseSerializer,
    OtpVerifySerializer,
    ReceiverRegisterSerializer,
    RefreshTokenSerializer,
    RestaurantRegisterSerializer,
)
from apps.common.exceptions import PeonyAPIException, success_response
from apps.common.schema import enveloped_schema


class OtpSendView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Auth"],
        summary="Send OTP",
        description="OTP expires after 1 minute.",
        request=OtpSendSerializer,
        responses={200: enveloped_schema(OtpSendResponseSerializer, "OtpSendEnvelope")},
    )
    def post(self, request):
        serializer = OtpSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = services.send_otp(**serializer.validated_data)
        return success_response(data)


class OtpVerifyView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Auth"],
        summary="Verify OTP",
        request=OtpVerifySerializer,
        responses={
            200: OpenApiResponse(
                response=enveloped_schema(
                    AuthTokensSerializer,
                    "OtpVerifyLoginEnvelope",
                    OtpVerifyRegistrationResponseSerializer,
                ),
                description="Returns JWT tokens (login) or a registration token (register).",
            )
        },
    )
    def post(self, request):
        serializer = OtpVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = services.verify_otp(**serializer.validated_data)
        return success_response(data)


class ReceiverRegisterView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Auth"],
        summary="Register receiver",
        parameters=[
            OpenApiParameter(
                name="Registration-Token",
                type=str,
                location=OpenApiParameter.HEADER,
                required=True,
            )
        ],
        request=ReceiverRegisterSerializer,
        responses={201: enveloped_schema(AuthTokensSerializer, "ReceiverRegisterEnvelope")},
    )
    def post(self, request):
        phone_e164 = _require_registration_token(request)
        serializer = ReceiverRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = services.register_receiver(phone_e164, **serializer.validated_data)
        return success_response(data, status_code=201)


class RestaurantRegisterView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Auth"],
        summary="Register restaurant",
        parameters=[
            OpenApiParameter(
                name="Registration-Token",
                type=str,
                location=OpenApiParameter.HEADER,
                required=True,
            )
        ],
        request=RestaurantRegisterSerializer,
        responses={201: enveloped_schema(AuthTokensSerializer, "RestaurantRegisterEnvelope")},
    )
    def post(self, request):
        phone_e164 = _require_registration_token(request)
        serializer = RestaurantRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = services.register_restaurant(phone_e164, serializer.validated_data)
        return success_response(data, status_code=201)


class DonorRegisterView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Auth"],
        summary="Register donor",
        parameters=[
            OpenApiParameter(
                name="Registration-Token",
                type=str,
                location=OpenApiParameter.HEADER,
                required=True,
            )
        ],
        request=DonorRegisterSerializer,
        responses={201: enveloped_schema(AuthTokensSerializer, "DonorRegisterEnvelope")},
    )
    def post(self, request):
        phone_e164 = _require_registration_token(request)
        serializer = DonorRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = services.register_donor(phone_e164, **serializer.validated_data)
        return success_response(data, status_code=201)


class TokenRefreshView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Auth"],
        summary="Refresh JWT",
        request=RefreshTokenSerializer,
        responses={200: enveloped_schema(RefreshTokenSerializer, "TokenRefreshEnvelope")},
    )
    def post(self, request):
        serializer = RefreshTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = services.refresh_access_token(serializer.validated_data["refresh"])
        return success_response(data)


class LogoutView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Auth"],
        summary="Logout",
        request=LogoutSerializer,
        responses={200: enveloped_schema(MessageResponseSerializer, "LogoutEnvelope")},
    )
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = services.logout(serializer.validated_data["refresh"])
        return success_response(data)


def _require_registration_token(request) -> str:
    token = request.headers.get("Registration-Token")
    if not token:
        raise PeonyAPIException(
            code="MISSING_REGISTRATION_TOKEN",
            message="Registration-Token header is required.",
            http_status=401,
        )
    return services.verify_registration_token(token)
