from django.urls import path

from apps.claims.receiver_views import ClaimDetailView, ClaimsView, TodayClaimStatusView
from apps.claims.review_views import RestaurantReviewView, ReviewTagsView

urlpatterns = [
    path("claims/today/", TodayClaimStatusView.as_view(), name="receiver-claims-today"),
    path("claims/", ClaimsView.as_view(), name="receiver-claims"),
    path("claims/<uuid:claim_id>/", ClaimDetailView.as_view(), name="receiver-claim-detail"),
    path("reviews/tags/", ReviewTagsView.as_view(), name="receiver-review-tags"),
    path(
        "restaurants/<uuid:restaurant_id>/review/",
        RestaurantReviewView.as_view(),
        name="receiver-restaurant-review",
    ),
]
