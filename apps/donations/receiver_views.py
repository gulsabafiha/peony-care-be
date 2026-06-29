from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.generics import GenericAPIView

from apps.accounts import receiver_services as account_receiver_services
from apps.common.exceptions import success_response
from apps.common.permissions import IsReceiver
from apps.common.schema import enveloped_schema
from apps.donations import receiver_services
from apps.donations.serializers import (
    FoodBrowseItemSerializer,
    FoodDetailSerializer,
    LocationQuerySerializer,
    RestaurantBrowseItemSerializer,
    SearchQuerySerializer,
)


def _resolve_location(request, validated_data) -> tuple[float, float, float]:
    return account_receiver_services.resolve_browse_context(
        request.user,
        validated_data.get("lat"),
        validated_data.get("lng"),
        validated_data.get("radius_km"),
    )


class BrowseFoodView(GenericAPIView):
    permission_classes = [IsReceiver]
    serializer_class = LocationQuerySerializer

    @extend_schema(
        tags=["Receiver"],
        summary="Browse nearby food",
        parameters=[
            OpenApiParameter("lat", float, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("lng", float, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("radius_km", float, OpenApiParameter.QUERY, required=False),
        ],
        responses={
            200: enveloped_schema(FoodBrowseItemSerializer, "BrowseFoodEnvelope", many=True)
        },
    )
    def get(self, request):
        serializer = self.get_serializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        lat, lng, radius_km = _resolve_location(request, serializer.validated_data)
        data = receiver_services.browse_food(lat, lng, radius_km)
        return success_response(data)


class SearchFoodView(GenericAPIView):
    permission_classes = [IsReceiver]
    serializer_class = SearchQuerySerializer

    @extend_schema(
        tags=["Receiver"],
        summary="Search and filter food",
        parameters=[
            OpenApiParameter("lat", float, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("lng", float, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("radius_km", float, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("q", str, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("category", str, OpenApiParameter.QUERY, required=False),
        ],
        responses={
            200: enveloped_schema(FoodBrowseItemSerializer, "SearchFoodEnvelope", many=True)
        },
    )
    def get(self, request):
        serializer = self.get_serializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data
        lat, lng, radius_km = _resolve_location(request, validated)
        data = receiver_services.search_food(
            lat=lat,
            lng=lng,
            radius_km=radius_km,
            query=validated.get("q", ""),
            category=validated.get("category"),
        )
        return success_response(data)


class BrowseRestaurantsView(GenericAPIView):
    permission_classes = [IsReceiver]
    serializer_class = LocationQuerySerializer

    @extend_schema(
        tags=["Receiver"],
        summary="Browse nearby restaurants",
        parameters=[
            OpenApiParameter("lat", float, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("lng", float, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("radius_km", float, OpenApiParameter.QUERY, required=False),
        ],
        responses={
            200: enveloped_schema(
                RestaurantBrowseItemSerializer,
                "BrowseRestaurantsEnvelope",
                many=True,
            )
        },
    )
    def get(self, request):
        serializer = self.get_serializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        lat, lng, radius_km = _resolve_location(request, serializer.validated_data)
        data = receiver_services.browse_restaurants(lat, lng, radius_km)
        return success_response(data)


class FoodDetailView(GenericAPIView):
    permission_classes = [IsReceiver]
    serializer_class = LocationQuerySerializer

    @extend_schema(
        tags=["Receiver"],
        summary="Food detail",
        parameters=[
            OpenApiParameter("lat", float, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("lng", float, OpenApiParameter.QUERY, required=False),
        ],
        responses={200: enveloped_schema(FoodDetailSerializer, "FoodDetailEnvelope")},
    )
    def get(self, request, food_id):
        serializer = self.get_serializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        lat, lng, _radius_km = _resolve_location(request, serializer.validated_data)
        data = receiver_services.get_food_detail(
            food_id=str(food_id),
            lat=lat,
            lng=lng,
        )
        return success_response(data)
