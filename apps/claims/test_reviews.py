from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import ReceiverProfile, RestaurantProfile, User
from apps.claims.models import FoodClaim, RestaurantReview
from apps.common.choices import ClaimStatus, ListStatus, UserRole
from apps.common.timezone_utils import now_sgt
from apps.donations.models import FoodItem

pytestmark = pytest.mark.django_db

RECEIVER_PHONE = "+6591111199"
REST_PHONE = "+6592222299"
LAT = 1.3521
LNG = 103.8198


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def receiver_user():
    user = User.objects.create_user(
        phone_e164=RECEIVER_PHONE,
        role=UserRole.RECEIVER,
        is_active=True,
    )
    ReceiverProfile.objects.create(
        user=user,
        display_name="Reviewer",
        latitude=LAT,
        longitude=LNG,
    )
    return user


@pytest.fixture
def restaurant_profile():
    user = User.objects.create_user(
        phone_e164=REST_PHONE,
        role=UserRole.RESTAURANT,
        is_active=True,
    )
    return RestaurantProfile.objects.create(
        user=user,
        name="Tian Tian Hainanese",
        uen="200912399A",
        address="443 Joo Chiat Rd, Singapore 427656",
        postal_code="427656",
        latitude=LAT,
        longitude=LNG,
        contact_name="Manager",
        contact_email="contact@restaurant.sg",
        is_approved=True,
    )


@pytest.fixture
def food_item(restaurant_profile):
    now = timezone.now()
    food = FoodItem.objects.create(
        restaurant=restaurant_profile,
        name="Chicken Rice",
        description="1 pack",
        category="RICE",
        unit="pack",
        quantity_original=5,
        quantity_available=4,
        quantity_claimed=1,
        pickup_start=now,
        pickup_end=now + timedelta(hours=2),
        food_qr_data="",
        list_status=ListStatus.ACTIVE,
    )
    food.food_qr_data = f"{food.id}|{restaurant_profile.id}|{int(now.timestamp())}"
    food.save(update_fields=["food_qr_data"])
    return food


@pytest.fixture
def collected_claim(receiver_user, restaurant_profile, food_item):
    now = now_sgt()
    return FoodClaim.objects.create(
        food=food_item,
        receiver=receiver_user,
        restaurant=restaurant_profile,
        claim_date=now.date(),
        claimed_at=now - timedelta(hours=1),
        collected_at=now,
        receiver_lat=LAT,
        receiver_lng=LNG,
        status=ClaimStatus.COLLECTED,
        quantity_claimed=1,
    )


def auth_client(api_client, user):
    token = str(RefreshToken.for_user(user).access_token)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return api_client


def review_url(restaurant_id):
    return reverse(
        "receiver_claims:receiver-restaurant-review",
        kwargs={"restaurant_id": restaurant_id},
    )


class TestRestaurantReviews:
    def test_list_review_tags(self, api_client, receiver_user):
        client = auth_client(api_client, receiver_user)
        response = client.get(reverse("receiver_claims:receiver-review-tags"))
        assert response.status_code == 200
        tags = response.json()["data"]
        codes = [tag["code"] for tag in tags]
        assert codes == [
            "friendly-staff",
            "fresh-tasty",
            "quick-pickup",
            "generous-portion",
            "clean-packaging",
        ]
        assert tags[0]["label"] == "Friendly staff"

    def test_get_review_form_without_review(
        self, api_client, receiver_user, restaurant_profile, collected_claim
    ):
        client = auth_client(api_client, receiver_user)
        response = client.get(review_url(restaurant_profile.id))
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["restaurant_name"] == "Tian Tian Hainanese"
        assert data["latest_food_name"] == "Chicken Rice"
        assert data["collected_label"] == "collected today"
        assert data["context_subtitle"] == "Chicken Rice · collected today"
        assert data["has_review"] is False
        assert data["review"] is None
        assert "claim_id" not in data
        assert "food_id" not in data
        assert len(data["tags"]) == 5

    def test_create_update_delete_review(
        self, api_client, receiver_user, restaurant_profile, collected_claim
    ):
        client = auth_client(api_client, receiver_user)
        url = review_url(restaurant_profile.id)

        create = client.post(
            url,
            {
                "rating": 4,
                "tag_codes": ["friendly-staff", "fresh-tasty"],
                "comment": "Warm staff and the food was still piping hot.",
            },
            format="json",
        )
        assert create.status_code == 201
        created = create.json()["data"]
        assert created["rating"] == 4
        assert created["rating_label"] == "Very good"
        assert created["restaurant_id"] == str(restaurant_profile.id)
        assert set(created["tag_codes"]) == {"friendly-staff", "fresh-tasty"}
        assert "claim_id" not in created
        assert (
            RestaurantReview.objects.filter(
                restaurant=restaurant_profile, receiver=receiver_user
            ).count()
            == 1
        )

        form = client.get(url)
        assert form.status_code == 200
        form_data = form.json()["data"]
        assert form_data["has_review"] is True
        assert form_data["review"]["rating"] == 4

        duplicate = client.post(
            url,
            {"rating": 5, "comment": "again"},
            format="json",
        )
        assert duplicate.status_code == 409

        update = client.patch(
            url,
            {
                "rating": 5,
                "tag_codes": ["quick-pickup"],
                "comment": "Updated note",
            },
            format="json",
        )
        assert update.status_code == 200
        updated = update.json()["data"]
        assert updated["rating"] == 5
        assert updated["rating_label"] == "Excellent"
        assert updated["tag_codes"] == ["quick-pickup"]
        assert updated["comment"] == "Updated note"

        detail = client.get(
            reverse(
                "receiver_donations:receiver-restaurant-detail",
                kwargs={"restaurant_id": restaurant_profile.id},
            ),
            {"lat": LAT, "lng": LNG},
        )
        assert detail.status_code == 200
        restaurant = detail.json()["data"]
        assert restaurant["rating"] == 5.0
        assert restaurant["review_count"] == 1
        assert restaurant["reviews_available"] is True
        assert restaurant["rating_display"] == "5.0"

        history = client.get(reverse("receiver_claims:receiver-claims"))
        assert history.status_code == 200
        items = history.json()["data"]["results"]
        assert items[0]["restaurant_id"] == str(restaurant_profile.id)
        assert items[0]["has_review"] is True
        assert items[0]["can_review"] is True

        delete = client.delete(url)
        assert delete.status_code == 200
        assert delete.json()["data"]["deleted"] is True
        assert delete.json()["data"]["restaurant_id"] == str(restaurant_profile.id)
        assert (
            RestaurantReview.objects.filter(
                restaurant=restaurant_profile, receiver=receiver_user
            ).count()
            == 0
        )

    def test_cannot_review_without_collected_claim(
        self, api_client, receiver_user, restaurant_profile, food_item
    ):
        client = auth_client(api_client, receiver_user)
        response = client.post(
            review_url(restaurant_profile.id),
            {"rating": 5},
            format="json",
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "NO_COLLECTED_CLAIM"

    def test_review_is_per_restaurant_not_per_food(
        self, api_client, receiver_user, restaurant_profile, collected_claim, food_item
    ):
        """Second collected food at same restaurant still shares one restaurant review."""
        now = now_sgt()
        other_food = FoodItem.objects.create(
            restaurant=restaurant_profile,
            name="Laksa",
            description="1 pack",
            category="NOODLES",
            unit="pack",
            quantity_original=3,
            quantity_available=2,
            quantity_claimed=1,
            pickup_start=now,
            pickup_end=now + timedelta(hours=2),
            food_qr_data="x",
            list_status=ListStatus.ACTIVE,
        )
        FoodClaim.objects.create(
            food=other_food,
            receiver=receiver_user,
            restaurant=restaurant_profile,
            claim_date=now.date(),
            claimed_at=now,
            collected_at=now,
            receiver_lat=LAT,
            receiver_lng=LNG,
            status=ClaimStatus.COLLECTED,
            quantity_claimed=1,
        )

        client = auth_client(api_client, receiver_user)
        url = review_url(restaurant_profile.id)
        create = client.post(url, {"rating": 4, "comment": "Great place"}, format="json")
        assert create.status_code == 201

        form = client.get(url)
        assert form.status_code == 200
        data = form.json()["data"]
        assert data["has_review"] is True
        assert data["latest_food_name"] == "Laksa"
        assert (
            RestaurantReview.objects.filter(
                receiver=receiver_user, restaurant=restaurant_profile
            ).count()
            == 1
        )
