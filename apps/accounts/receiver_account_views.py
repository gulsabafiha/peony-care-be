from django.http import HttpResponse
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.generics import GenericAPIView

from apps.accounts import receiver_account_services
from apps.accounts.receiver_account_serializers import (
    DataExportResponseSerializer,
    DeleteAccountResponseSerializer,
    DeleteAccountSerializer,
)
from apps.common.exceptions import success_response
from apps.common.permissions import IsReceiver
from apps.common.schema import enveloped_schema


class DeleteAccountView(GenericAPIView):
    permission_classes = [IsReceiver]
    serializer_class = DeleteAccountSerializer

    @extend_schema(
        tags=["Receiver"],
        summary="Delete receiver account",
        description='Permanently deletes the account. Requires confirmation text "DELETE".',
        request=DeleteAccountSerializer,
        responses={200: enveloped_schema(DeleteAccountResponseSerializer, "DeleteAccountEnvelope")},
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        receiver_account_services.delete_receiver_account(
            request.user,
            confirmation=serializer.validated_data["confirmation"],
        )
        return success_response(
            {"deleted": True},
            message="Your account has been permanently deleted.",
        )


class DownloadDataExportView(GenericAPIView):
    permission_classes = [IsReceiver]

    @extend_schema(
        tags=["Receiver"],
        summary="Download personal data as PDF",
        description="Instantly generates and downloads a PDF export of all personal data.",
        responses={
            (200, "application/pdf"): OpenApiResponse(description="PDF file download"),
        },
    )
    def get(self, request):
        pdf_bytes = receiver_account_services.generate_data_export_pdf(request.user)
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="peonycare-my-data.pdf"'
        return response


class RequestDataExportView(GenericAPIView):
    permission_classes = [IsReceiver]

    @extend_schema(
        tags=["Receiver"],
        summary="Request personal data export",
        description="Generates a PDF immediately and returns a download URL.",
        request=None,
        responses={
            201: enveloped_schema(DataExportResponseSerializer, "RequestDataExportEnvelope")
        },
    )
    def post(self, request):
        data = receiver_account_services.request_data_export(
            request.user,
            request=request,
        )
        return success_response(
            data,
            status_code=201,
            message="Your data export is ready. Use the download URL to save your PDF.",
        )
