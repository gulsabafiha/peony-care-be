from drf_spectacular.utils import extend_schema
from rest_framework.generics import GenericAPIView

from apps.claims import review_services
from apps.claims.serializers import (
    CreateRestaurantReviewSerializer,
    DeleteRestaurantReviewSerializer,
    RestaurantReviewFormSerializer,
    RestaurantReviewSerializer,
    ReviewTagSerializer,
    UpdateRestaurantReviewSerializer,
)
from apps.common.exceptions import success_response
from apps.common.permissions import IsReceiver
from apps.common.schema import enveloped_schema


class ReviewTagsView(GenericAPIView):
    permission_classes = [IsReceiver]

    @extend_schema(
        tags=["Receiver"],
        summary="List review tags",
        responses={
            200: enveloped_schema(ReviewTagSerializer, "ReviewTagsEnvelope", many=True)
        },
    )
    def get(self, request):
        data = review_services.list_review_tags()
        return success_response(data)


class RestaurantReviewView(GenericAPIView):
    permission_classes = [IsReceiver]

    @extend_schema(
        tags=["Receiver"],
        summary="Get restaurant review form / existing review",
        responses={
            200: enveloped_schema(
                RestaurantReviewFormSerializer,
                "RestaurantReviewFormEnvelope",
            )
        },
    )
    def get(self, request, restaurant_id):
        data = review_services.get_review_form(request.user, str(restaurant_id))
        return success_response(data)

    @extend_schema(
        tags=["Receiver"],
        summary="Submit a restaurant review",
        request=CreateRestaurantReviewSerializer,
        responses={
            201: enveloped_schema(
                RestaurantReviewSerializer,
                "CreateRestaurantReviewEnvelope",
            )
        },
    )
    def post(self, request, restaurant_id):
        serializer = CreateRestaurantReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = review_services.create_review(
            request.user,
            str(restaurant_id),
            **serializer.validated_data,
        )
        return success_response(data, status_code=201)

    @extend_schema(
        tags=["Receiver"],
        summary="Update a restaurant review",
        request=UpdateRestaurantReviewSerializer,
        responses={
            200: enveloped_schema(
                RestaurantReviewSerializer,
                "UpdateRestaurantReviewEnvelope",
            )
        },
    )
    def patch(self, request, restaurant_id):
        serializer = UpdateRestaurantReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = review_services.update_review(
            request.user,
            str(restaurant_id),
            **serializer.validated_data,
        )
        return success_response(data)

    @extend_schema(
        tags=["Receiver"],
        summary="Delete a restaurant review",
        responses={
            200: enveloped_schema(
                DeleteRestaurantReviewSerializer,
                "DeleteRestaurantReviewEnvelope",
            )
        },
    )
    def delete(self, request, restaurant_id):
        data = review_services.delete_review(request.user, str(restaurant_id))
        return success_response(data)
