from django.http import HttpResponse
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.generics import GenericAPIView

from apps.accounts import restaurant_account_services
from apps.accounts.receiver_account_serializers import (
    DataExportResponseSerializer,
    DeleteAccountResponseSerializer,
    DeleteAccountSerializer,
)
from apps.common.exceptions import success_response
from apps.common.permissions import IsRestaurant
from apps.common.schema import enveloped_schema


class RestaurantDeleteAccountView(GenericAPIView):
    permission_classes = [IsRestaurant]
    serializer_class = DeleteAccountSerializer

    @extend_schema(
        tags=["Restaurant"],
        summary="Delete restaurant account",
        description='Permanently deletes the account. Requires confirmation text "DELETE".',
        request=DeleteAccountSerializer,
        responses={
            200: enveloped_schema(DeleteAccountResponseSerializer, "RestaurantDeleteAccountEnvelope")
        },
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = restaurant_account_services.delete_restaurant_account(
            request.user,
            confirmation=serializer.validated_data["confirmation"],
        )
        return success_response(
            data,
            message="Your restaurant account has been permanently deleted.",
        )


class RestaurantDownloadDataExportView(GenericAPIView):
    permission_classes = [IsRestaurant]

    @extend_schema(
        tags=["Restaurant"],
        summary="Download restaurant data as PDF",
        description="Instantly generates and downloads a PDF export of restaurant data.",
        responses={
            (200, "application/pdf"): OpenApiResponse(description="PDF file download"),
        },
    )
    def get(self, request):
        pdf_bytes = restaurant_account_services.generate_data_export_pdf(request.user)
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = (
            'attachment; filename="peonycare-restaurant-data.pdf"'
        )
        return response


class RestaurantRequestDataExportView(GenericAPIView):
    permission_classes = [IsRestaurant]

    @extend_schema(
        tags=["Restaurant"],
        summary="Request restaurant data export",
        description="Generates a PDF immediately and returns a download URL.",
        request=None,
        responses={
            201: enveloped_schema(
                DataExportResponseSerializer, "RestaurantRequestDataExportEnvelope"
            )
        },
    )
    def post(self, request):
        data = restaurant_account_services.request_data_export(
            request.user,
            request=request,
        )
        return success_response(
            data,
            status_code=201,
            message="Your data export is ready. Use the download URL to save your PDF.",
        )
