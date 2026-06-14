from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import RestaurantProfile, User
from apps.common.choices import ListStatus, UserRole
from apps.donations.models import FoodItem

pytestmark = pytest.mark.django_db

REST_PHONE = "+6592222222"
LAT = 1.3521
LNG = 103.8198


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def restaurant_user():
    user = User.objects.create_user(
        phone_e164=REST_PHONE,
        role=UserRole.RESTAURANT,
        is_active=True,
    )
    RestaurantProfile.objects.create(
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
    return user


def auth_client(api_client, user):
    token = str(RefreshToken.for_user(user).access_token)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return api_client


class TestRestaurantDonations:
    def test_dashboard(self, api_client, restaurant_user):
        client = auth_client(api_client, restaurant_user)
        response = client.get(reverse("restaurant_donations:restaurant-dashboard"))
        assert response.status_code == 200
        assert "active_count" in response.json()["data"]

    def test_create_and_list_donation(self, api_client, restaurant_user):
        client = auth_client(api_client, restaurant_user)
        now = timezone.now()
        response = client.post(
            reverse("restaurant_donations:restaurant-donations"),
            {
                "name": "Chicken Rice",
                "description": "1 pack",
                "category": "RICE",
                "quantity": 5,
                "pickup_start": now.isoformat(),
                "pickup_end": (now + timedelta(hours=2)).isoformat(),
            },
            format="json",
        )
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["food_qr_data"]
        assert "|" in data["food_qr_data"]

        list_response = client.get(
            reverse("restaurant_donations:restaurant-donations"),
            {"status": "active"},
        )
        assert list_response.status_code == 200
        assert len(list_response.json()["data"]) == 1

    def test_unapproved_restaurant_cannot_post(self, api_client):
        user = User.objects.create_user(
            phone_e164="+6593333333",
            role=UserRole.RESTAURANT,
            is_active=True,
        )
        RestaurantProfile.objects.create(
            user=user,
            name="Pending Restaurant",
            uen="200912345B",
            address="1 Test Rd, Singapore 123456",
            postal_code="123456",
            latitude=LAT,
            longitude=LNG,
            contact_name="Owner",
            is_approved=False,
        )
        client = auth_client(api_client, user)
        now = timezone.now()
        response = client.post(
            reverse("restaurant_donations:restaurant-donations"),
            {
                "name": "Noodles",
                "category": "NOODLES",
                "quantity": 2,
                "pickup_start": now.isoformat(),
                "pickup_end": (now + timedelta(hours=2)).isoformat(),
            },
            format="json",
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "RESTAURANT_NOT_APPROVED"

    def test_close_reactivate_delete_flow(self, api_client, restaurant_user):
        client = auth_client(api_client, restaurant_user)
        now = timezone.now()
        create = client.post(
            reverse("restaurant_donations:restaurant-donations"),
            {
                "name": "Bread",
                "category": "BREAD",
                "quantity": 1,
                "pickup_start": now.isoformat(),
                "pickup_end": (now + timedelta(hours=3)).isoformat(),
            },
            format="json",
        )
        food_id = create.json()["data"]["id"]

        close = client.post(
            reverse("restaurant_donations:restaurant-donation-close", kwargs={"food_id": food_id})
        )
        assert close.status_code == 200
        assert close.json()["data"]["list_status"] == ListStatus.INACTIVE

        reactivate = client.post(
            reverse(
                "restaurant_donations:restaurant-donation-reactivate",
                kwargs={"food_id": food_id},
            )
        )
        assert reactivate.status_code == 200
        assert reactivate.json()["data"]["list_status"] == ListStatus.ACTIVE

        client.post(
            reverse("restaurant_donations:restaurant-donation-close", kwargs={"food_id": food_id})
        )
        delete = client.delete(
            reverse("restaurant_donations:restaurant-donation-detail", kwargs={"food_id": food_id})
        )
        assert delete.status_code == 200
        assert FoodItem.objects.filter(id=food_id).count() == 0

    def test_get_donation_detail(self, api_client, restaurant_user):
        client = auth_client(api_client, restaurant_user)
        now = timezone.now()
        create = client.post(
            reverse("restaurant_donations:restaurant-donations"),
            {
                "name": "Noodles",
                "description": "2 packs",
                "category": "NOODLES",
                "quantity": 3,
                "pickup_start": now.isoformat(),
                "pickup_end": (now + timedelta(hours=2)).isoformat(),
            },
            format="json",
        )
        food_id = create.json()["data"]["id"]

        response = client.get(
            reverse("restaurant_donations:restaurant-donation-detail", kwargs={"food_id": food_id})
        )
        assert response.status_code == 200
        detail = response.json()["data"]
        assert detail["name"] == "Noodles"
        assert detail["quantity_available"] == 3
        assert "claims" in detail

    def test_patch_donation(self, api_client, restaurant_user):
        client = auth_client(api_client, restaurant_user)
        now = timezone.now()
        create = client.post(
            reverse("restaurant_donations:restaurant-donations"),
            {
                "name": "Snacks",
                "category": "SNACKS",
                "quantity": 4,
                "pickup_start": now.isoformat(),
                "pickup_end": (now + timedelta(hours=2)).isoformat(),
            },
            format="json",
        )
        food_id = create.json()["data"]["id"]

        response = client.patch(
            reverse("restaurant_donations:restaurant-donation-detail", kwargs={"food_id": food_id}),
            {"name": "Updated Snacks", "quantity": 6},
            format="json",
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["name"] == "Updated Snacks"
        assert data["quantity_available"] == 6


class TestRestaurantProfile:
    def test_profile_and_approval_status(self, api_client, restaurant_user):
        client = auth_client(api_client, restaurant_user)

        profile = client.get(reverse("restaurant_donations:restaurant-profile"))
        assert profile.status_code == 200
        assert profile.json()["data"]["name"] == "Tian Tian Hainanese"

        status = client.get(reverse("restaurant_donations:restaurant-approval-status"))
        assert status.status_code == 200
        assert status.json()["data"]["is_approved"] is True

    def test_patch_profile(self, api_client, restaurant_user):
        client = auth_client(api_client, restaurant_user)
        response = client.patch(
            reverse("restaurant_donations:restaurant-profile"),
            {
                "contact_name": "New Manager",
                "about": "Family-run since 1990",
                "opening_hours": "10am - 9pm",
            },
            format="json",
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["contact_name"] == "New Manager"
        assert data["about"] == "Family-run since 1990"
        assert data["opening_hours"] == "10am - 9pm"

    def test_public_restaurant_page(self, api_client, restaurant_user):
        restaurant = restaurant_user.restaurant_profile
        response = api_client.get(
            reverse("public-restaurant", kwargs={"restaurant_id": restaurant.id})
        )
        assert response.status_code == 200
        assert response.json()["data"]["name"] == "Tian Tian Hainanese"
