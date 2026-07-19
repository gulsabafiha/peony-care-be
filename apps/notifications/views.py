from drf_spectacular.utils import extend_schema
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated

from apps.common.exceptions import success_response
from apps.common.schema import enveloped_schema
from apps.notifications import services
from apps.notifications.serializers import UnreadCountSerializer


class UnreadCountView(GenericAPIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Notifications"],
        summary="Unread notification count",
        responses={200: enveloped_schema(UnreadCountSerializer, "UnreadCountEnvelope")},
    )
    def get(self, request):
        return success_response(services.get_unread_count(request.user))
