from django.urls import path

from apps.donations.restaurant_views import (
    ApprovalStatusView,
    DashboardView,
    DonationCloseView,
    DonationDetailView,
    DonationListCreateView,
    DonationReactivateView,
    RestaurantProfileView,
)

urlpatterns = [
    path("dashboard/", DashboardView.as_view(), name="restaurant-dashboard"),
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
    path("approval-status/", ApprovalStatusView.as_view(), name="restaurant-approval-status"),
    path("profile/", RestaurantProfileView.as_view(), name="restaurant-profile"),
]
