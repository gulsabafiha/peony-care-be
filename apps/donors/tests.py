from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import DonorProfile, RestaurantProfile, User
from apps.common.choices import CreditPreference, MealOrderStatus, MoneyDonationStatus, UserRole
from apps.donations.models import FoodItem, MenuItem
from apps.donors.models import MealOrder, MoneyDonation

pytestmark = pytest.mark.django_db

DONOR_PHONE = "+6593333333"
REST_PHONE = "+6592222222"
LAT = 1.3521
LNG = 103.8198


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def donor_user():
    user = User.objects.create_user(
        phone_e164=DONOR_PHONE,
        role=UserRole.DONOR,
        is_active=True,
    )
    DonorProfile.objects.create(
        user=user,
        display_name="James Tan",
        contact_email="james@example.com",
        credit_preference=CreditPreference.SHOW_NAME,
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
def menu_item(restaurant_profile):
    return MenuItem.objects.create(
        restaurant=restaurant_profile,
        name="Chicken Rice",
        description="1 pack",
        price_sgd=Decimal("5.50"),
        is_available=True,
        sort_order=1,
    )


def auth_client(api_client, user):
    token = str(RefreshToken.for_user(user).access_token)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return api_client


class TestDonorProfile:
    def test_get_and_update_profile(self, api_client, donor_user):
        client = auth_client(api_client, donor_user)
        response = client.get(reverse("donor-profile"))
        assert response.status_code == 200
        assert response.json()["data"]["display_name"] == "James Tan"

        patch_response = client.patch(
            reverse("donor-profile"),
            {"display_name": "JT", "contact_email": "jt@example.com"},
            format="json",
        )
        assert patch_response.status_code == 200
        assert patch_response.json()["data"]["display_name"] == "JT"
        assert patch_response.json()["data"]["contact_email"] == "jt@example.com"


class TestDonorCreditPreference:
    def test_get_and_update_credit_preference(self, api_client, donor_user):
        client = auth_client(api_client, donor_user)
        response = client.get(reverse("donor-credit-preference"))
        assert response.status_code == 200
        assert response.json()["data"]["credit_preference"] == CreditPreference.SHOW_NAME

        patch_response = client.patch(
            reverse("donor-credit-preference"),
            {"credit_preference": CreditPreference.ANONYMOUS},
            format="json",
        )
        assert patch_response.status_code == 200
        assert patch_response.json()["data"]["credit_preference"] == CreditPreference.ANONYMOUS


class TestDonorDashboard:
    def test_dashboard(self, api_client, donor_user):
        client = auth_client(api_client, donor_user)
        response = client.get(reverse("donor-dashboard"))
        assert response.status_code == 200
        data = response.json()["data"]
        assert "total_meals_sponsored" in data
        assert "recent_donations" in data


class TestDonorRestaurants:
    def test_browse_and_menu(self, api_client, donor_user, restaurant_profile, menu_item):
        client = auth_client(api_client, donor_user)
        browse = client.get(reverse("donor-restaurants"))
        assert browse.status_code == 200
        restaurants = browse.json()["data"]
        assert len(restaurants) == 1
        assert restaurants[0]["menu_item_count"] == 1

        menu = client.get(
            reverse("donor-restaurant-menu", kwargs={"restaurant_id": restaurant_profile.id})
        )
        assert menu.status_code == 200
        menu_data = menu.json()["data"]
        assert menu_data["restaurant_name"] == restaurant_profile.name
        assert len(menu_data["menu_items"]) == 1
        assert menu_data["menu_items"][0]["name"] == "Chicken Rice"


class TestMealOrders:
    def test_create_meal_order_posts_food(
        self, api_client, donor_user, restaurant_profile, menu_item
    ):
        client = auth_client(api_client, donor_user)
        now = timezone.now()
        response = client.post(
            reverse("donor-meal-orders"),
            {
                "restaurant_id": str(restaurant_profile.id),
                "items": [{"menu_item_id": str(menu_item.id), "quantity": 2}],
                "pickup_start": now.isoformat(),
                "pickup_end": (now + timedelta(hours=2)).isoformat(),
            },
            format="json",
        )
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["status"] == MealOrderStatus.POSTED
        assert data["food_item"]["quantity_available"] == 2
        assert data["food_item"]["food_qr_data"]
        assert MealOrder.objects.count() == 1
        assert FoodItem.objects.filter(individual_donor=donor_user.donor_profile).count() == 1

        donor_user.donor_profile.refresh_from_db()
        assert donor_user.donor_profile.total_meals_sponsored == 2

        history = client.get(reverse("donor-history"))
        assert history.status_code == 200
        assert history.json()["data"][0]["type"] == "MEAL"


class TestMoneyDonations:
    def test_create_and_confirm_transfer(self, api_client, donor_user):
        client = auth_client(api_client, donor_user)
        response = client.post(
            reverse("donor-money-donations"),
            {"amount_sgd": "25.00", "is_anonymous": False},
            format="json",
        )
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["status"] == MoneyDonationStatus.PENDING_TRANSFER
        assert data["reference_code"].startswith("PNY-")
        assert "paynow" in data

        donation_id = data["id"]
        confirm = client.post(
            reverse("donor-money-donation-confirm", kwargs={"donation_id": donation_id})
        )
        assert confirm.status_code == 200
        assert confirm.json()["data"]["transfer_marked_at"]

        repeat = client.post(
            reverse("donor-money-donation-confirm", kwargs={"donation_id": donation_id})
        )
        assert repeat.status_code == 409

    def test_impact_after_admin_confirm(self, api_client, donor_user):
        client = auth_client(api_client, donor_user)
        create = client.post(
            reverse("donor-money-donations"),
            {"amount_sgd": "10.00"},
            format="json",
        )
        donation = MoneyDonation.objects.get(id=create.json()["data"]["id"])
        donation.status = MoneyDonationStatus.CONFIRMED
        donation.confirmed_at = timezone.now()
        donation.save()
        donor_user.donor_profile.total_amount_donated_sgd = Decimal("10.00")
        donor_user.donor_profile.save()

        impact = client.get(reverse("donor-impact"))
        assert impact.status_code == 200
        impact_data = impact.json()["data"]
        assert impact_data["total_amount_donated_sgd"] == "10.00"
        assert len(impact_data["monthly"]) == 1
