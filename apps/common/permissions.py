from rest_framework.permissions import BasePermission

from apps.common.choices import UserRole


class IsReceiver(BasePermission):
    def has_permission(self, request, view):
        return (
            bool(request.user and request.user.is_authenticated)
            and request.user.role == UserRole.RECEIVER
        )
