from django.urls import path

from apps.donors.views import (
    CreditPreferenceView,
    DashboardView,
    DonorProfileView,
    HistoryView,
    ImpactView,
    MealOrderCreateView,
    MoneyDonationConfirmTransferView,
    MoneyDonationCreateView,
    RestaurantBrowseView,
    RestaurantMenuView,
)

urlpatterns = [
    path("dashboard/", DashboardView.as_view(), name="donor-dashboard"),
    path("history/", HistoryView.as_view(), name="donor-history"),
    path("impact/", ImpactView.as_view(), name="donor-impact"),
    path("credit-preference/", CreditPreferenceView.as_view(), name="donor-credit-preference"),
    path("profile/", DonorProfileView.as_view(), name="donor-profile"),
    path("restaurants/", RestaurantBrowseView.as_view(), name="donor-restaurants"),
    path(
        "restaurants/<uuid:restaurant_id>/menu/",
        RestaurantMenuView.as_view(),
        name="donor-restaurant-menu",
    ),
    path("meal-orders/", MealOrderCreateView.as_view(), name="donor-meal-orders"),
    path("money-donations/", MoneyDonationCreateView.as_view(), name="donor-money-donations"),
    path(
        "money-donations/<uuid:donation_id>/confirm-transfer/",
        MoneyDonationConfirmTransferView.as_view(),
        name="donor-money-donation-confirm",
    ),
]
