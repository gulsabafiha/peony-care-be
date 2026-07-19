from django.urls import path

from apps.claims.restaurant_views import (
    ClaimReportView,
    DonationClaimsView,
    MarkClaimCollectedView,
    MarkClaimNoShowView,
    TodayClaimsBoardView,
    UndoClaimNoShowView,
)

urlpatterns = [
    path("claims/today/", TodayClaimsBoardView.as_view(), name="restaurant-claims-today"),
    path(
        "claims/<uuid:claim_id>/collect/",
        MarkClaimCollectedView.as_view(),
        name="restaurant-claim-collect",
    ),
    path(
        "claims/<uuid:claim_id>/no-show/",
        MarkClaimNoShowView.as_view(),
        name="restaurant-claim-no-show",
    ),
    path(
        "claims/<uuid:claim_id>/undo-no-show/",
        UndoClaimNoShowView.as_view(),
        name="restaurant-claim-undo-no-show",
    ),
    path(
        "claims/<uuid:claim_id>/report/",
        ClaimReportView.as_view(),
        name="restaurant-claim-report",
    ),
    path(
        "donations/<uuid:food_id>/claims/",
        DonationClaimsView.as_view(),
        name="restaurant-donation-claims",
    ),
]
