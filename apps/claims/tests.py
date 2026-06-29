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
def report_reason():
    from apps.donations.models import FoodReportReasonOption

    option, _ = FoodReportReasonOption.objects.get_or_create(
        code="unsafe-or-spoiled",
        defaults={
            "label": "Food was unsafe or spoiled",
            "sort_order": 1,
            "is_active": True,
        },
    )
    return option


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

    def test_browse_uses_profile_location_by_default(self, api_client, receiver_user, food_item):
        client = auth_client(api_client, receiver_user)
        response = client.get(reverse("receiver_donations:receiver-browse"))
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) == 1
        assert data[0]["name"] == "Chicken Rice"

    def test_browse_uses_profile_radius_by_default(
        self, api_client, receiver_user, restaurant_profile, food_item
    ):
        client = auth_client(api_client, receiver_user)
        receiver_user.receiver_profile.browse_radius_km = 1.0
        receiver_user.receiver_profile.save(update_fields=["browse_radius_km"])

        far_user = User.objects.create_user(
            phone_e164="+6593333333",
            role=UserRole.RESTAURANT,
            is_active=True,
        )
        far_restaurant = RestaurantProfile.objects.create(
            user=far_user,
            name="Far Restaurant",
            uen="200912345C",
            address="Far away",
            postal_code="888888",
            latitude=1.4,
            longitude=104.0,
            contact_name="Owner",
            is_approved=True,
        )
        now = timezone.now()
        FoodItem.objects.create(
            restaurant=far_restaurant,
            name="Far Meal",
            category="RICE",
            quantity_original=2,
            quantity_available=2,
            pickup_start=now,
            pickup_end=now + timedelta(hours=2),
            list_status=ListStatus.ACTIVE,
        )

        response = client.get(reverse("receiver_donations:receiver-browse"))
        assert response.status_code == 200
        names = [item["name"] for item in response.json()["data"]]
        assert "Chicken Rice" in names
        assert "Far Meal" not in names

    def test_browse_restaurants(self, api_client, receiver_user, food_item):
        client = auth_client(api_client, receiver_user)
        response = client.get(reverse("receiver_donations:receiver-restaurants-browse"))
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) == 1
        assert data[0]["name"] == "Tian Tian Hainanese"
        assert data[0]["active_meal_count"] == 1
        assert data[0]["distance_km"] == 0.0

    def test_restaurant_detail(self, api_client, receiver_user, restaurant_profile, food_item):
        client = auth_client(api_client, receiver_user)
        response = client.get(
            reverse(
                "receiver_donations:receiver-restaurant-detail",
                kwargs={"restaurant_id": restaurant_profile.id},
            ),
            {"lat": LAT, "lng": LNG},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["name"] == "Tian Tian Hainanese"
        assert data["distance_km"] == 0.0
        assert data["active_meal_count"] == 1
        assert data["categories"] == ["Rice"]
        assert len(data["available_meals"]) == 1
        meal = data["available_meals"][0]
        assert meal["name"] == "Chicken Rice"
        assert meal["quantity_available"] == 5
        assert meal["sponsorship_type"] == "DIRECT"

    def test_restaurant_detail_not_found(self, api_client, receiver_user):
        client = auth_client(api_client, receiver_user)
        response = client.get(
            reverse(
                "receiver_donations:receiver-restaurant-detail",
                kwargs={"restaurant_id": "00000000-0000-0000-0000-000000000001"},
            ),
            {"lat": LAT, "lng": LNG},
        )
        assert response.status_code == 404

    def test_submit_food_report(self, api_client, receiver_user, food_item, report_reason):
        client = auth_client(api_client, receiver_user)
        response = client.post(
            reverse(
                "receiver_donations:receiver-food-report",
                kwargs={"food_id": food_item.id},
            ),
            {
                "reason_id": str(report_reason.id),
                "comment": "Food smelled bad on pickup.",
            },
            format="json",
        )
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["food_name"] == "Chicken Rice"
        assert data["restaurant_name"] == "Tian Tian Hainanese"
        assert data["reason_id"] == str(report_reason.id)
        assert data["reason_code"] == "unsafe-or-spoiled"
        assert data["reason_label"] == "Food was unsafe or spoiled"
        assert "confidential" in response.json()["message"].lower()

        from apps.donations.models import FoodReport

        assert FoodReport.objects.filter(reporter=receiver_user).count() == 1

    def test_list_food_report_reasons(self, api_client, receiver_user, report_reason):
        client = auth_client(api_client, receiver_user)
        response = client.get(reverse("receiver_donations:receiver-report-reasons"))
        assert response.status_code == 200
        reasons = response.json()["data"]
        assert len(reasons) >= 1
        assert reasons[0]["id"] == str(report_reason.id)
        assert reasons[0]["code"] == "unsafe-or-spoiled"
        assert "label" in reasons[0]


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
            {
                "display_name": "Sarah T.",
                "latitude": 1.3,
                "longitude": 103.9,
                "browse_radius_km": 10,
            },
            format="json",
        )
        assert response.status_code == 200
        profile = response.json()["data"]
        assert profile["display_name"] == "Sarah T."
        assert profile["latitude"] == 1.3
        assert profile["longitude"] == 103.9
        assert profile["browse_radius_km"] == 10

    def test_upload_profile_photo(self, api_client, receiver_user):
        from django.core.files.uploadedfile import SimpleUploadedFile

        client = auth_client(api_client, receiver_user)
        photo = SimpleUploadedFile(
            "profile.jpg",
            b"fake-image-content",
            content_type="image/jpeg",
        )
        response = client.patch(
            reverse("receiver_accounts:receiver-profile"),
            {"photo": photo},
            format="multipart",
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["photo_url"] is not None
        assert "/media/receivers/" in data["photo_url"]

        response = client.patch(
            reverse("receiver_accounts:receiver-profile"),
            {"remove_photo": True},
            format="multipart",
        )
        assert response.status_code == 200
        assert response.json()["data"]["photo_url"] is None

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


class TestReceiverLocationSettings:
    def test_get_and_update_location_settings(self, api_client, receiver_user):
        client = auth_client(api_client, receiver_user)
        response = client.get(reverse("receiver_accounts:receiver-location-settings"))
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["browse_radius_km"] == 5.0
        assert data["radius_options_km"] == [1, 2, 3, 5, 10]
        assert data["location_services_enabled"] is True
        assert data["save_location_history"] is True

        response = client.patch(
            reverse("receiver_accounts:receiver-location-settings"),
            {
                "browse_radius_km": 10,
                "location_services_enabled": False,
            },
            format="json",
        )
        assert response.status_code == 200
        updated = response.json()["data"]
        assert updated["browse_radius_km"] == 10
        assert updated["location_services_enabled"] is False

    def test_location_history_and_clear(self, api_client, receiver_user):
        client = auth_client(api_client, receiver_user)
        response = client.post(
            reverse("receiver_accounts:receiver-location-history"),
            {
                "place_name": "Maxwell Food Centre",
                "area_label": "Tanjong Pagar · 1 Kadayanallur St",
                "place_type": "FOOD_CENTRE",
                "latitude": 1.2804,
                "longitude": 103.8444,
            },
            format="json",
        )
        assert response.status_code == 201
        assert response.json()["data"]["place_name"] == "Maxwell Food Centre"

        response = client.get(reverse("receiver_accounts:receiver-location-settings"))
        assert response.json()["data"]["recent_places_count"] == 1

        response = client.delete(reverse("receiver_accounts:receiver-location-history"))
        assert response.status_code == 200
        assert response.json()["data"]["cleared"] is True

        response = client.get(reverse("receiver_accounts:receiver-location-settings"))
        assert response.json()["data"]["recent_places_count"] == 0
