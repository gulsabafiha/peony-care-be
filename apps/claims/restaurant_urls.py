from django.urls import path

from apps.claims.restaurant_views import DonationClaimsView, TodayClaimsBoardView

urlpatterns = [
    path("claims/today/", TodayClaimsBoardView.as_view(), name="restaurant-claims-today"),
    path(
        "donations/<uuid:food_id>/claims/",
        DonationClaimsView.as_view(),
        name="restaurant-donation-claims",
    ),
]
