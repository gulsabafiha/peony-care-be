from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


class PeonyAPIException(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        details: dict | None = None,
        http_status: int = 400,
    ):
        self.code = code
        self.message = message
        self.details = details or {}
        self.http_status = http_status
        super().__init__(message)


def success_response(data, status_code=status.HTTP_200_OK, message: str | None = None) -> Response:
    body = {
        "status": "success",
        "data": data,
        "error": None,
        "timestamp": timezone.now().isoformat(),
    }
    if message is not None:
        body["message"] = message
    return Response(body, status=status_code)


def error_response(
    code: str,
    message: str,
    details: dict | None = None,
    status_code: int = status.HTTP_400_BAD_REQUEST,
) -> Response:
    return Response(
        {
            "status": "error",
            "data": None,
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            },
            "timestamp": timezone.now().isoformat(),
        },
        status=status_code,
    )


def custom_exception_handler(exc, context):
    if isinstance(exc, PeonyAPIException):
        return error_response(
            code=exc.code,
            message=exc.message,
            details=exc.details,
            status_code=exc.http_status,
        )

    response = exception_handler(exc, context)
    if response is not None:
        code = "VALIDATION_ERROR" if response.status_code == 400 else "REQUEST_ERROR"
        message = "Request could not be processed."
        details = response.data if isinstance(response.data, dict) else {"detail": response.data}
        return error_response(
            code=code,
            message=message,
            details=details,
            status_code=response.status_code,
        )

    return response
