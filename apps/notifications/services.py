from apps.accounts.models import User
from apps.notifications.models import Notification


def get_unread_count(user: User) -> dict:
    return {
        "unread_count": Notification.objects.filter(user=user, read_at__isnull=True).count(),
    }
