from django.urls import path

from apps.donations.receiver_views import (
    BrowseFoodView,
    BrowseRestaurantsView,
    FoodDetailView,
    SearchFoodView,
)

urlpatterns = [
    path("donations/browse/", BrowseFoodView.as_view(), name="receiver-browse"),
    path("donations/search/", SearchFoodView.as_view(), name="receiver-search"),
    path("restaurants/browse/", BrowseRestaurantsView.as_view(), name="receiver-restaurants-browse"),
    path("donations/<uuid:food_id>/", FoodDetailView.as_view(), name="receiver-food-detail"),
]
