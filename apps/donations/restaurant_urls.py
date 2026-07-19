from django.urls import path

from apps.donations.restaurant_views import (
    AnalyticsView,
    ApprovalStatusView,
    DashboardView,
    DonationCloseView,
    DonationDetailView,
    DonationListCreateView,
    DonationReactivateView,
    LocationConfirmView,
    LocationReverseView,
    LocationSearchView,
    MenuPhotoDetailView,
    MenuPhotoListCreateView,
    MenuPhotoReorderView,
    RestaurantProfileView,
)

urlpatterns = [
    path("dashboard/", DashboardView.as_view(), name="restaurant-dashboard"),
    path("analytics/", AnalyticsView.as_view(), name="restaurant-analytics"),
    path("donations/", DonationListCreateView.as_view(), name="restaurant-donations"),
    path(
        "donations/<uuid:food_id>/",
        DonationDetailView.as_view(),
        name="restaurant-donation-detail",
    ),
    path(
        "donations/<uuid:food_id>/close/",
        DonationCloseView.as_view(),
        name="restaurant-donation-close",
    ),
    path(
        "donations/<uuid:food_id>/reactivate/",
        DonationReactivateView.as_view(),
        name="restaurant-donation-reactivate",
    ),
    path("location/search/", LocationSearchView.as_view(), name="restaurant-location-search"),
    path("location/reverse/", LocationReverseView.as_view(), name="restaurant-location-reverse"),
    path("location/confirm/", LocationConfirmView.as_view(), name="restaurant-location-confirm"),
    path("menu-photos/", MenuPhotoListCreateView.as_view(), name="restaurant-menu-photos"),
    path(
        "menu-photos/reorder/",
        MenuPhotoReorderView.as_view(),
        name="restaurant-menu-photos-reorder",
    ),
    path(
        "menu-photos/<uuid:photo_id>/",
        MenuPhotoDetailView.as_view(),
        name="restaurant-menu-photo-detail",
    ),
    path("approval-status/", ApprovalStatusView.as_view(), name="restaurant-approval-status"),
    path("profile/", RestaurantProfileView.as_view(), name="restaurant-profile"),
]
