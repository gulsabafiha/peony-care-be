from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import ReceiverProfile, RestaurantProfile, User
from apps.claims.models import FoodClaim
from apps.common.choices import ClaimStatus, ListStatus, UserRole
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
    ReceiverProfile.objects.create(
        user=user,
        display_name="Sarah Mun",
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


class TestRestaurantClaimsBoard:
    def test_today_claims_board(self, api_client, restaurant_profile, receiver_user, food_item):
        from apps.claims.services import create_claim

        create_claim(
            receiver=receiver_user,
            food_id=str(food_item.id),
            qr_payload=food_item.food_qr_data,
            lat=LAT,
            lng=LNG,
        )

        client = auth_client(api_client, restaurant_profile.user)
        response = client.get(reverse("restaurant_claims:restaurant-claims-today"))
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total"] == 1
        assert data["claims"][0]["receiver_name"] == "Sarah Mun"

    def test_donation_claims_list(self, api_client, restaurant_profile, receiver_user, food_item):
        FoodClaim.objects.create(
            food=food_item,
            receiver=receiver_user,
            restaurant=restaurant_profile,
            claim_date=timezone.localdate(),
            claimed_at=timezone.now(),
            receiver_lat=LAT,
            receiver_lng=LNG,
            status=ClaimStatus.CLAIMED,
        )
        client = auth_client(api_client, restaurant_profile.user)
        response = client.get(
            reverse(
                "restaurant_claims:restaurant-donation-claims",
                kwargs={"food_id": food_item.id},
            )
        )
        assert response.status_code == 200
        assert response.json()["data"]["total"] == 1
