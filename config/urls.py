from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.common.views import health_check

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health_check, name="health-check"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path(
        "api/v1/receiver/",
        include(("apps.donations.urls", "receiver_donations"), namespace="receiver_donations"),
    ),
    path(
        "api/v1/receiver/",
        include(("apps.claims.urls", "receiver_claims"), namespace="receiver_claims"),
    ),
    path(
        "api/v1/receiver/",
        include(
            ("apps.accounts.receiver_urls", "receiver_accounts"),
            namespace="receiver_accounts",
        ),
    ),
    path("api/v1/restaurant/", include("apps.donations.urls")),
    path("api/v1/restaurant/", include("apps.claims.urls")),
    path("api/v1/donor/", include("apps.donors.urls")),
    path("api/v1/", include("apps.notifications.urls")),
]
