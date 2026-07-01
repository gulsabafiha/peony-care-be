from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

import config.admin  # noqa: F401

from apps.common.views import health_check
from apps.donations.restaurant_views import PublicRestaurantView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health_check, name="health-check"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path(
        "api/v1/receiver/",
        include(
            ("apps.donations.receiver_urls", "receiver_donations"),
            namespace="receiver_donations",
        ),
    ),
    path(
        "api/v1/receiver/",
        include(("apps.claims.receiver_urls", "receiver_claims"), namespace="receiver_claims"),
    ),
    path(
        "api/v1/receiver/",
        include(
            ("apps.accounts.receiver_urls", "receiver_accounts"),
            namespace="receiver_accounts",
        ),
    ),
    path(
        "api/v1/restaurant/",
        include(
            ("apps.donations.restaurant_urls", "restaurant_donations"),
            namespace="restaurant_donations",
        ),
    ),
    path(
        "api/v1/restaurant/",
        include(
            ("apps.claims.restaurant_urls", "restaurant_claims"),
            namespace="restaurant_claims",
        ),
    ),
    path(
        "api/v1/restaurants/<uuid:restaurant_id>/",
        PublicRestaurantView.as_view(),
        name="public-restaurant",
    ),
    path("api/v1/donor/", include("apps.donors.urls")),
    path("api/v1/", include("apps.notifications.urls")),
]

if settings.DEBUG:
    from django.conf.urls.static import static

    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
