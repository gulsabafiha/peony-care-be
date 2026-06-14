from django.urls import path

from apps.claims.receiver_views import ClaimDetailView, ClaimsView, TodayClaimStatusView

urlpatterns = [
    path("claims/today/", TodayClaimStatusView.as_view(), name="receiver-claims-today"),
    path("claims/", ClaimsView.as_view(), name="receiver-claims"),
    path("claims/<uuid:claim_id>/", ClaimDetailView.as_view(), name="receiver-claim-detail"),
]
