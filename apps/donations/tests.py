from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import RestaurantProfile, User
from apps.common.choices import ClosedReason, FoodStatus, ListStatus, UserRole
from apps.donations.models import FoodItem
from apps.notifications.models import Notification

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
        now = timezone.now()
        client.post(
            reverse("restaurant_donations:restaurant-donations"),
            {
                "name": "Chicken Rice",
                "category": "RICE",
                "quantity": 5,
                "pickup_start": now.isoformat(),
                "pickup_end": (now + timedelta(hours=2)).isoformat(),
                "recurrence_type": "DAILY",
            },
            format="json",
        )
        response = client.get(reverse("restaurant_donations:restaurant-dashboard"))
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["active_count"] == 1
        assert data["restaurant"]["name"] == "Tian Tian Hainanese"
        assert data["restaurant"]["initials"] == "TT"
        assert "impact" in data
        assert "week_over_week_pct" in data["impact"]
        assert "today" in data
        assert "this_week" in data
        assert data["today"]["active_count"] == 1
        assert data["unread_alerts_count"] == 0
        assert data["active_donations"]["groups"]
        assert data["today_listings"][0]["recurrence_label"] == "Daily"

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
                "recurrence_type": "CUSTOM",
                "recurrence_days": [0, 1, 2, 3, 4, 5],
            },
            format="json",
        )
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["food_qr_data"]
        assert "|" in data["food_qr_data"]
        assert data["recurrence_label"] == "Mon, Tue, Wed, Thu, Fri, Sat"
        assert data["percent_claimed"] == 0

        list_response = client.get(
            reverse("restaurant_donations:restaurant-donations"),
            {"status": "active"},
        )
        assert list_response.status_code == 200
        payload = list_response.json()["data"]
        assert payload["summary"]["active_count"] == 1
        assert payload["summary"]["past_count"] == 0
        assert payload["summary"]["inactive_count"] == 0
        assert len(payload["groups"]) == 1
        assert len(payload["groups"][0]["items"]) == 1

    def test_restaurant_can_post_without_admin_approval(self, api_client):
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
        assert response.status_code == 201
        assert response.json()["data"]["name"] == "Noodles"

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
        closed = close.json()["data"]
        assert closed["list_status"] == ListStatus.INACTIVE
        assert closed["paused_ago"]
        assert closed["closed_at"]

        inactive_list = client.get(
            reverse("restaurant_donations:restaurant-donations"),
            {"status": "inactive"},
        )
        assert inactive_list.status_code == 200
        inactive_payload = inactive_list.json()["data"]
        assert inactive_payload["summary"]["inactive_count"] == 1
        assert inactive_payload["summary"]["subtitle"]
        assert len(inactive_payload["groups"][0]["items"]) == 1

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


class TestRestaurantDonationsPast:
    def test_past_list_grouped_with_summary(self, api_client, restaurant_user):
        restaurant = restaurant_user.restaurant_profile
        now = timezone.now()
        FoodItem.objects.create(
            restaurant=restaurant,
            name="Nasi Lemak",
            category="RICE",
            quantity_original=8,
            quantity_available=0,
            quantity_claimed=8,
            status=FoodStatus.FULLY_CLAIMED,
            list_status=ListStatus.PAST,
            pickup_start=now - timedelta(days=1, hours=2),
            pickup_end=now - timedelta(days=1),
            closed_at=now - timedelta(days=1),
            closed_reason=ClosedReason.FULLY_CLAIMED,
        )
        FoodItem.objects.create(
            restaurant=restaurant,
            name="Bread Set",
            category="BREAD",
            quantity_original=6,
            quantity_available=0,
            quantity_claimed=4,
            status=FoodStatus.EXPIRED,
            list_status=ListStatus.PAST,
            pickup_start=now - timedelta(days=2, hours=2),
            pickup_end=now - timedelta(days=2),
            closed_at=now - timedelta(days=2),
            closed_reason=ClosedReason.EXPIRED,
        )

        client = auth_client(api_client, restaurant_user)
        response = client.get(
            reverse("restaurant_donations:restaurant-donations"),
            {"status": "past"},
        )
        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["summary"]["past_count"] == 2
        assert payload["summary"]["meals_this_week"] is not None
        assert len(payload["groups"]) >= 1
        items = [item for group in payload["groups"] for item in group["items"]]
        bread = next(item for item in items if item["name"] == "Bread Set")
        assert bread["percent_claimed"] == 67
        assert bread["expired_count"] == 2
        nasi = next(item for item in items if item["name"] == "Nasi Lemak")
        assert nasi["is_done"] is True
        assert nasi["percent_claimed"] == 100


class TestNotificationsUnreadCount:
    def test_unread_count(self, api_client, restaurant_user):
        Notification.objects.create(
            user=restaurant_user,
            type="FOOD_CLAIMED",
            title="New claim",
            body="Someone claimed your food",
        )
        client = auth_client(api_client, restaurant_user)
        response = client.get(reverse("notifications-unread-count"))
        assert response.status_code == 200
        assert response.json()["data"]["unread_count"] == 1

        dashboard = client.get(reverse("restaurant_donations:restaurant-dashboard"))
        assert dashboard.json()["data"]["unread_alerts_count"] == 1


class TestRestaurantProfile:
    def test_profile_and_approval_status(self, api_client, restaurant_user):
        client = auth_client(api_client, restaurant_user)

        profile = client.get(reverse("restaurant_donations:restaurant-profile"))
        assert profile.status_code == 200
        assert profile.json()["data"]["name"] == "Tian Tian Hainanese"
        assert profile.json()["data"]["initials"] == "TT"

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
