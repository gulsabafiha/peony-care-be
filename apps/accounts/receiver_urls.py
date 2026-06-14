from django.urls import path

from apps.accounts.receiver_views import ReceiverProfileView, ReceiverStatsView

urlpatterns = [
    path("profile/", ReceiverProfileView.as_view(), name="receiver-profile"),
    path("stats/", ReceiverStatsView.as_view(), name="receiver-stats"),
]
