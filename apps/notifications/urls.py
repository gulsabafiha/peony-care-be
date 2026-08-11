from django.urls import path

from apps.notifications.views import (
    MarkAllNotificationsReadView,
    MarkNotificationReadView,
    NotificationListView,
    UnreadCountView,
)

urlpatterns = [
    path(
        "notifications/unread-count/",
        UnreadCountView.as_view(),
        name="notifications-unread-count",
    ),
    path(
        "notifications/read-all/",
        MarkAllNotificationsReadView.as_view(),
        name="notifications-read-all",
    ),
    path(
        "notifications/<uuid:notification_id>/read/",
        MarkNotificationReadView.as_view(),
        name="notifications-mark-read",
    ),
    path(
        "notifications/",
        NotificationListView.as_view(),
        name="notifications-list",
    ),
]
