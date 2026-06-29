from drf_spectacular.utils import PolymorphicProxySerializer, inline_serializer
from rest_framework import serializers

STANDARD_ERROR_RESPONSE_REF = "#/components/schemas/StandardErrorEnvelope"


def enveloped_schema(data_serializer, envelope_name: str, *alt_serializers, many: bool = False):
    """Wrap a response serializer in the Peony Care API envelope for OpenAPI."""
    data_types = [data_serializer, *alt_serializers]
    if len(data_types) > 1:
        data_field = PolymorphicProxySerializer(
            component_name=f"{envelope_name}Data",
            serializers=data_types,
            many=many,
            resource_type_field_name=None,
        )
    elif many:
        data_field = data_serializer(many=True)
    else:
        data_field = data_serializer

    return inline_serializer(
        name=envelope_name,
        fields={
            "status": serializers.CharField(default="success"),
            "data": data_field,
            "error": serializers.CharField(allow_null=True, default=None),
            "timestamp": serializers.DateTimeField(),
        },
    )


def add_standard_error_response(result, generator, request, public):
    """Document the shared Peony Care error envelope on every OpenAPI operation."""
    schemas = result.setdefault("components", {}).setdefault("schemas", {})
    schemas.setdefault(
        "StandardErrorDetail",
        {
            "type": "object",
            "required": ["code", "message", "details"],
            "properties": {
                "code": {
                    "type": "string",
                    "example": "VALIDATION_ERROR",
                },
                "message": {
                    "type": "string",
                    "example": "Request could not be processed.",
                },
                "details": {
                    "type": "object",
                    "additionalProperties": True,
                    "example": {"field": ["This field is required."]},
                },
            },
        },
    )
    schemas.setdefault(
        "StandardErrorEnvelope",
        {
            "type": "object",
            "required": ["status", "data", "error", "timestamp"],
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["error"],
                    "example": "error",
                },
                "data": {
                    "type": "object",
                    "nullable": True,
                    "example": None,
                },
                "error": {
                    "$ref": "#/components/schemas/StandardErrorDetail",
                },
                "timestamp": {
                    "type": "string",
                    "format": "date-time",
                },
            },
        },
    )

    for path_item in result.get("paths", {}).values():
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            operation.setdefault("responses", {}).setdefault(
                "default",
                {
                    "description": "Standard error response.",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": STANDARD_ERROR_RESPONSE_REF},
                        }
                    },
                },
            )

    return result
