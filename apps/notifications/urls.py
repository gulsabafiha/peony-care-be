from django.urls import path

from apps.notifications.views import UnreadCountView

urlpatterns = [
    path(
        "notifications/unread-count/",
        UnreadCountView.as_view(),
        name="notifications-unread-count",
    ),
]
