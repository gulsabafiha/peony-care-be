from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import ReceiverProfile, RestaurantProfile, User
from apps.claims.models import FoodClaim
from apps.common.choices import ListStatus, UserRole
from apps.donations.models import FoodItem

pytestmark = pytest.mark.django_db

RECEIVER_PHONE = "+6591111111"
REST_PHONE = "+6592222222"
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
    ReceiverProfile.objects.create(user=user, display_name="Sarah Mun")
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
        uen="200912345A",
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
        quantity_available=5,
        quantity_claimed=0,
        pickup_start=now,
        pickup_end=now + timedelta(hours=2),
        food_qr_data="",
        list_status=ListStatus.ACTIVE,
    )
    food.food_qr_data = f"{food.id}|{restaurant_profile.id}|{int(now.timestamp())}"
    food.save(update_fields=["food_qr_data"])
    return food


def auth_client(api_client, user):
    token = str(RefreshToken.for_user(user).access_token)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return api_client


class TestBrowseAndSearch:
    def test_browse_nearby_food(self, api_client, receiver_user, food_item):
        client = auth_client(api_client, receiver_user)
        response = client.get(
            reverse("receiver_donations:receiver-browse"),
            {"lat": LAT, "lng": LNG, "radius_km": 5},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) == 1
        assert data[0]["name"] == "Chicken Rice"
        assert data[0]["distance_km"] == 0.0

    def test_search_by_name(self, api_client, receiver_user, food_item):
        client = auth_client(api_client, receiver_user)
        response = client.get(
            reverse("receiver_donations:receiver-search"),
            {"lat": LAT, "lng": LNG, "q": "Chicken"},
        )
        assert response.status_code == 200
        assert len(response.json()["data"]) == 1

    def test_food_detail(self, api_client, receiver_user, food_item):
        client = auth_client(api_client, receiver_user)
        response = client.get(
            reverse("receiver_donations:receiver-food-detail", kwargs={"food_id": food_item.id}),
            {"lat": LAT, "lng": LNG},
        )
        assert response.status_code == 200
        detail = response.json()["data"]
        assert detail["claim_progress"]["remaining"] == 5


class TestClaims:
    def test_daily_limit_before_claim(self, api_client, receiver_user):
        client = auth_client(api_client, receiver_user)
        response = client.get(reverse("receiver_claims:receiver-claims-today"))
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["used"] == 0
        assert data["can_claim"] is True

    def test_create_claim(self, api_client, receiver_user, food_item):
        client = auth_client(api_client, receiver_user)
        response = client.post(
            reverse("receiver_claims:receiver-claims"),
            {
                "food_id": str(food_item.id),
                "qr_payload": food_item.food_qr_data,
                "lat": LAT,
                "lng": LNG,
            },
            format="json",
        )
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["status"] == "CLAIMED"
        assert data["restaurant_name"] == "Tian Tian Hainanese"

        food_item.refresh_from_db()
        assert food_item.quantity_available == 4
        assert FoodClaim.objects.filter(receiver=receiver_user).count() == 1

    def test_daily_limit_blocks_second_claim(self, api_client, receiver_user, restaurant_profile):
        client = auth_client(api_client, receiver_user)
        now = timezone.now()

        for i in range(2):
            food = FoodItem.objects.create(
                restaurant=restaurant_profile,
                name=f"Meal {i}",
                category="RICE",
                quantity_original=1,
                quantity_available=1,
                pickup_start=now,
                pickup_end=now + timedelta(hours=2),
                food_qr_data="",
                list_status=ListStatus.ACTIVE,
            )
            food.food_qr_data = f"{food.id}|{restaurant_profile.id}|{int(now.timestamp())}"
            food.save(update_fields=["food_qr_data"])

            response = client.post(
                reverse("receiver_claims:receiver-claims"),
                {
                    "food_id": str(food.id),
                    "qr_payload": food.food_qr_data,
                    "lat": LAT,
                    "lng": LNG,
                },
                format="json",
            )
            if i == 0:
                assert response.status_code == 201
            else:
                assert response.status_code == 429
                assert response.json()["error"]["code"] == "DAILY_LIMIT_REACHED"

    def test_claim_history(self, api_client, receiver_user, food_item):
        client = auth_client(api_client, receiver_user)
        client.post(
            reverse("receiver_claims:receiver-claims"),
            {
                "food_id": str(food_item.id),
                "qr_payload": food_item.food_qr_data,
                "lat": LAT,
                "lng": LNG,
            },
            format="json",
        )
        response = client.get(reverse("receiver_claims:receiver-claims"))
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["count"] == 1
        assert len(data["grouped_by_week"]) == 1

    def test_claim_detail(self, api_client, receiver_user, food_item):
        client = auth_client(api_client, receiver_user)
        create = client.post(
            reverse("receiver_claims:receiver-claims"),
            {
                "food_id": str(food_item.id),
                "qr_payload": food_item.food_qr_data,
                "lat": LAT,
                "lng": LNG,
            },
            format="json",
        )
        assert create.status_code == 201
        claim_id = FoodClaim.objects.get(receiver=receiver_user).id

        response = client.get(
            reverse("receiver_claims:receiver-claim-detail", kwargs={"claim_id": claim_id})
        )
        assert response.status_code == 200
        detail = response.json()["data"]
        assert detail["status"] == "CLAIMED"
        assert detail["restaurant_name"] == "Tian Tian Hainanese"
        assert detail["food"]["name"] == "Chicken Rice"


class TestReceiverProfile:
    def test_get_and_update_profile(self, api_client, receiver_user):
        client = auth_client(api_client, receiver_user)

        response = client.get(reverse("receiver_accounts:receiver-profile"))
        assert response.status_code == 200
        assert response.json()["data"]["display_name"] == "Sarah Mun"

        response = client.patch(
            reverse("receiver_accounts:receiver-profile"),
            {"display_name": "Sarah T."},
            format="json",
        )
        assert response.status_code == 200
        assert response.json()["data"]["display_name"] == "Sarah T."

    def test_stats(self, api_client, receiver_user, food_item):
        client = auth_client(api_client, receiver_user)
        client.post(
            reverse("receiver_claims:receiver-claims"),
            {
                "food_id": str(food_item.id),
                "qr_payload": food_item.food_qr_data,
                "lat": LAT,
                "lng": LNG,
            },
            format="json",
        )
        response = client.get(reverse("receiver_accounts:receiver-stats"))
        assert response.status_code == 200
        assert response.json()["data"]["lifetime_meals"] == 1

    def test_receiver_only(self, api_client, restaurant_profile):
        client = auth_client(api_client, restaurant_profile.user)
        response = client.get(reverse("receiver_accounts:receiver-profile"))
        assert response.status_code == 403
