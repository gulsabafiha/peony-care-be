from django.urls import path

from apps.accounts.location_settings_views import (
    ReceiverLocationHistoryView,
    ReceiverLocationSettingsView,
)
from apps.accounts.receiver_views import ReceiverProfileView, ReceiverStatsView

urlpatterns = [
    path("profile/", ReceiverProfileView.as_view(), name="receiver-profile"),
    path("stats/", ReceiverStatsView.as_view(), name="receiver-stats"),
    path("settings/location/", ReceiverLocationSettingsView.as_view(), name="receiver-location-settings"),
    path(
        "settings/location/history/",
        ReceiverLocationHistoryView.as_view(),
        name="receiver-location-history",
    ),
]
