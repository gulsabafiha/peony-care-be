from drf_spectacular.utils import PolymorphicProxySerializer, inline_serializer
from rest_framework import serializers


def enveloped_schema(data_serializer, envelope_name: str, *alt_serializers):
    """Wrap a response serializer in the Peony Care API envelope for OpenAPI."""
    data_types = [data_serializer, *alt_serializers]
    if len(data_types) > 1:
        data_field = PolymorphicProxySerializer(
            component_name=f"{envelope_name}Data",
            serializers=data_types,
            resource_type_field_name=None,
        )
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
