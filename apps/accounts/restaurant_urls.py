from django.urls import path

from apps.accounts.restaurant_account_views import (
    RestaurantDeleteAccountView,
    RestaurantDownloadDataExportView,
    RestaurantRequestDataExportView,
)
from apps.notifications.views import RestaurantNotificationSettingsView

urlpatterns = [
    path(
        "notifications/settings/",
        RestaurantNotificationSettingsView.as_view(),
        name="restaurant-notification-settings",
    ),
    path(
        "account/delete/",
        RestaurantDeleteAccountView.as_view(),
        name="restaurant-account-delete",
    ),
    path(
        "account/data-export/download/",
        RestaurantDownloadDataExportView.as_view(),
        name="restaurant-data-export-download",
    ),
    path(
        "account/data-export/",
        RestaurantRequestDataExportView.as_view(),
        name="restaurant-data-export",
    ),
]
