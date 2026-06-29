from django.urls import path

from apps.donations.receiver_views import (
    BrowseFoodView,
    BrowseRestaurantsView,
    FoodDetailView,
    FoodReportReasonsView,
    ReportFoodView,
    RestaurantDetailView,
    SearchFoodView,
)

urlpatterns = [
    path("donations/browse/", BrowseFoodView.as_view(), name="receiver-browse"),
    path("donations/search/", SearchFoodView.as_view(), name="receiver-search"),
    path("reports/reasons/", FoodReportReasonsView.as_view(), name="receiver-report-reasons"),
    path("restaurants/browse/", BrowseRestaurantsView.as_view(), name="receiver-restaurants-browse"),
    path(
        "restaurants/<uuid:restaurant_id>/",
        RestaurantDetailView.as_view(),
        name="receiver-restaurant-detail",
    ),
    path(
        "donations/<uuid:food_id>/report/",
        ReportFoodView.as_view(),
        name="receiver-food-report",
    ),
    path("donations/<uuid:food_id>/", FoodDetailView.as_view(), name="receiver-food-detail"),
]
