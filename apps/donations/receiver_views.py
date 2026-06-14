from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.generics import GenericAPIView

from apps.common.exceptions import success_response
from apps.common.permissions import IsReceiver
from apps.common.schema import enveloped_schema
from apps.donations import receiver_services
from apps.donations.serializers import (
    FoodBrowseItemSerializer,
    FoodDetailSerializer,
    LocationQuerySerializer,
    SearchQuerySerializer,
)


class BrowseFoodView(GenericAPIView):
    permission_classes = [IsReceiver]
    serializer_class = LocationQuerySerializer

    @extend_schema(
        tags=["Receiver"],
        summary="Browse nearby food",
        parameters=[
            OpenApiParameter("lat", float, OpenApiParameter.QUERY, required=True),
            OpenApiParameter("lng", float, OpenApiParameter.QUERY, required=True),
            OpenApiParameter("radius_km", float, OpenApiParameter.QUERY, required=False),
        ],
        responses={
            200: enveloped_schema(FoodBrowseItemSerializer, "BrowseFoodEnvelope", many=True)
        },
    )
    def get(self, request):
        serializer = self.get_serializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = receiver_services.browse_food(**serializer.validated_data)
        return success_response(data)


class SearchFoodView(GenericAPIView):
    permission_classes = [IsReceiver]
    serializer_class = SearchQuerySerializer

    @extend_schema(
        tags=["Receiver"],
        summary="Search and filter food",
        parameters=[
            OpenApiParameter("lat", float, OpenApiParameter.QUERY, required=True),
            OpenApiParameter("lng", float, OpenApiParameter.QUERY, required=True),
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
        data = receiver_services.search_food(
            lat=validated["lat"],
            lng=validated["lng"],
            radius_km=validated.get("radius_km"),
            query=validated.get("q", ""),
            category=validated.get("category"),
        )
        return success_response(data)


class FoodDetailView(GenericAPIView):
    permission_classes = [IsReceiver]
    serializer_class = LocationQuerySerializer

    @extend_schema(
        tags=["Receiver"],
        summary="Food detail",
        parameters=[
            OpenApiParameter("lat", float, OpenApiParameter.QUERY, required=True),
            OpenApiParameter("lng", float, OpenApiParameter.QUERY, required=True),
        ],
        responses={200: enveloped_schema(FoodDetailSerializer, "FoodDetailEnvelope")},
    )
    def get(self, request, food_id):
        serializer = self.get_serializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = receiver_services.get_food_detail(
            food_id=str(food_id),
            lat=serializer.validated_data["lat"],
            lng=serializer.validated_data["lng"],
        )
        return success_response(data)
