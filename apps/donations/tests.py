from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import ReceiverProfile, RestaurantProfile, User
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
                "notes": "Contains sesame. Packed hot.",
                "category": "RICE",
                "quantity": 5,
                "unit": "packs",
                "pickup_start": now.isoformat(),
                "pickup_end": (now + timedelta(hours=2)).isoformat(),
                "schedule": "custom_days",
                "recurrence_days": [0, 1, 2, 3, 4, 5],
            },
            format="json",
        )
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["food_qr_data"]
        assert "|" in data["food_qr_data"]
        assert data["description"] == "Contains sesame. Packed hot."
        assert data["recurrence_label"] == "Mon, Tue, Wed, Thu, Fri, Sat"
        assert data["percent_claimed"] == 0
        assert data["success_message"] == "Donation posted"
        assert data["summary"]["title"] == "Chicken Rice"
        assert data["summary"]["subtitle"] == "5 packs · Rice"
        assert data["restaurant"]["name"] == "Tian Tian Hainanese"
        assert "receivers within" in data["estimated_reach_label"]
        assert isinstance(data["estimated_reach"], int)

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

    def test_create_donation_with_photo(self, api_client, restaurant_user):
        from django.core.files.uploadedfile import SimpleUploadedFile

        client = auth_client(api_client, restaurant_user)
        now = timezone.now()
        photo = SimpleUploadedFile(
            "chicken.jpg",
            b"\xff\xd8\xff\xe0" + b"0" * 64,
            content_type="image/jpeg",
        )
        response = client.post(
            reverse("restaurant_donations:restaurant-donations"),
            {
                "name": "Chicken Rice",
                "category": "RICE",
                "quantity": 5,
                "pickup_start": now.isoformat(),
                "pickup_end": (now + timedelta(hours=2)).isoformat(),
                "schedule": "one-time",
                "photo": photo,
            },
            format="multipart",
        )
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["photo_url"]
        assert "/media/foods/" in data["photo_url"]
        assert data["recurrence_type"] == "NONE"

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
                "recurrence_type": "DAILY",
                "source_note": "Surplus from today's service.",
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
        assert detail["quantity_left"] == 3
        assert detail["quantity_left_label"] == "3 left to claim"
        assert detail["time_until_close"]
        assert detail["recurrence_badge"] == "Repeats daily"
        assert "Auto-posts every day" in detail["recurrence_schedule_summary"]
        assert detail["source"]["label"] == "Self-donated"
        assert detail["actions"]["can_pause"] is True
        assert detail["actions"]["can_delete"] is True
        assert "claims" in detail

    def test_delete_active_donation(self, api_client, restaurant_user):
        client = auth_client(api_client, restaurant_user)
        now = timezone.now()
        create = client.post(
            reverse("restaurant_donations:restaurant-donations"),
            {
                "name": "Temp Bowl",
                "category": "OTHER",
                "quantity": 1,
                "pickup_start": now.isoformat(),
                "pickup_end": (now + timedelta(hours=2)).isoformat(),
            },
            format="json",
        )
        food_id = create.json()["data"]["id"]
        delete = client.delete(
            reverse("restaurant_donations:restaurant-donation-detail", kwargs={"food_id": food_id})
        )
        assert delete.status_code == 200
        assert FoodItem.objects.filter(id=food_id).count() == 0

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


class TestRestaurantAnalytics:
    def test_analytics_empty_state(self, api_client, restaurant_user):
        client = auth_client(api_client, restaurant_user)
        response = client.get(reverse("restaurant_donations:restaurant-analytics"))
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["is_empty"] is True
        assert data["empty_state"]["title"] == "No analytics yet"
        assert data["selected_range"] == "30D"
        assert data["range_options"] == ["7D", "30D", "3M", "1Y", "ALL"]
        assert data["impact"]["people_fed"] == 0
        assert data["impact"]["claim_rate_display"] == "—"
        assert data["impact"]["sponsored_display"] == "S$0"
        assert data["meals_donated"]["has_data"] is False
        assert data["donation_source"]["total"] == 0
        assert len(data["claim_activity_heatmap"]["weeks"]) == 4

    def test_analytics_populated(self, api_client, restaurant_user):
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
            },
            format="json",
        )
        response = client.get(
            reverse("restaurant_donations:restaurant-analytics"),
            {"range": "30D"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["is_empty"] is False
        assert data["empty_state"] is None
        assert data["selected_range"] == "30D"
        assert data["total_impact"]["donations"] == 1
        assert data["impact"]["donations_posted"] == 1
        assert "week_over_week_label" in data["total_impact"]
        assert "weeks" in data["claim_rate_trend"]
        assert "direct" in data["donation_source"]
        assert "sponsored" in data["donation_source"]
        assert isinstance(data["most_claimed_dishes"], list)
        assert isinstance(data["sponsors"], list)


class TestRestaurantLocation:
    def test_search_reverse_confirm_location(self, api_client, restaurant_user):
        client = auth_client(api_client, restaurant_user)

        search = client.get(
            reverse("restaurant_donations:restaurant-location-search"),
            {"q": "427656"},
        )
        assert search.status_code == 200
        results = search.json()["data"]["results"]
        assert results
        assert results[0]["postal_code"] == "427656"
        assert results[0]["latitude"] == 1.30680

        reverse_lookup = client.get(
            reverse("restaurant_donations:restaurant-location-reverse"),
            {"lat": 1.30680, "lng": 103.90090},
        )
        assert reverse_lookup.status_code == 200
        selected = reverse_lookup.json()["data"]
        assert selected["address_line"] == "443 Joo Chiat Road"
        assert selected["snapped"] is True

        confirm = client.post(
            reverse("restaurant_donations:restaurant-location-confirm"),
            {
                "address": selected["address"],
                "address_line": selected["address_line"],
                "postal_code": selected["postal_code"],
                "latitude": selected["latitude"],
                "longitude": selected["longitude"],
            },
            format="json",
        )
        assert confirm.status_code == 200
        confirmed = confirm.json()["data"]
        assert confirmed["selected_location"]["postal_code"] == "427656"
        assert confirmed["restaurant"]["latitude"] == 1.30680
        assert confirmed["restaurant"]["longitude"] == 103.90090


class TestRestaurantMenuPhotos:
    def test_menu_photos_empty_upload_reorder_delete(self, api_client, restaurant_user):
        from django.core.files.uploadedfile import SimpleUploadedFile

        client = auth_client(api_client, restaurant_user)
        empty = client.get(reverse("restaurant_donations:restaurant-menu-photos"))
        assert empty.status_code == 200
        empty_data = empty.json()["data"]
        assert empty_data["is_empty"] is True
        assert empty_data["uploaded_count"] == 0
        assert empty_data["slots_left"] == 10
        assert empty_data["photos"] == []

        photo_a = SimpleUploadedFile(
            "menu-a.jpg",
            b"\xff\xd8\xff\xe0" + b"a" * 64,
            content_type="image/jpeg",
        )
        photo_b = SimpleUploadedFile(
            "menu-b.jpg",
            b"\xff\xd8\xff\xe0" + b"b" * 64,
            content_type="image/jpeg",
        )
        created = client.post(
            reverse("restaurant_donations:restaurant-menu-photos"),
            {"photos": [photo_a, photo_b]},
            format="multipart",
        )
        assert created.status_code == 201
        created_data = created.json()["data"]
        assert created_data["uploaded_count"] == 2
        assert created_data["slots_left"] == 8
        assert created_data["is_empty"] is False
        assert created_data["counter_label"] == "2 uploaded · max 10"
        assert "8 slots left" in created_data["add_slot_label"]
        assert len(created_data["donor_preview"]["photos"]) == 2
        ids = [item["id"] for item in created_data["photos"]]
        assert created_data["photos"][0]["sort_order"] == 1
        assert "/media/menu-photos/" in created_data["photos"][0]["photo_url"]

        reordered = client.patch(
            reverse("restaurant_donations:restaurant-menu-photos-reorder"),
            {"photo_ids": [ids[1], ids[0]]},
            format="json",
        )
        assert reordered.status_code == 200
        reordered_ids = [item["id"] for item in reordered.json()["data"]["photos"]]
        assert reordered_ids == [ids[1], ids[0]]
        assert reordered.json()["data"]["photos"][0]["position"] == 1

        deleted = client.delete(
            reverse(
                "restaurant_donations:restaurant-menu-photo-detail",
                kwargs={"photo_id": ids[1]},
            )
        )
        assert deleted.status_code == 200
        deleted_data = deleted.json()["data"]
        assert deleted_data["uploaded_count"] == 1
        assert deleted_data["photos"][0]["id"] == ids[0]
        assert deleted_data["photos"][0]["sort_order"] == 1


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


class TestNearbyReceiverNotifications:
    def test_create_donation_notifies_nearby_receivers(self, api_client, restaurant_user):
        nearby_user = User.objects.create_user(
            phone_e164="+6591111111",
            role=UserRole.RECEIVER,
            is_active=True,
        )
        ReceiverProfile.objects.create(
            user=nearby_user,
            display_name="Nearby Receiver",
            latitude=LAT,
            longitude=LNG,
            browse_radius_km=5.0,
            location_services_enabled=True,
        )

        far_user = User.objects.create_user(
            phone_e164="+6591111112",
            role=UserRole.RECEIVER,
            is_active=True,
        )
        ReceiverProfile.objects.create(
            user=far_user,
            display_name="Far Receiver",
            latitude=1.4500,
            longitude=103.8200,
            browse_radius_km=5.0,
            location_services_enabled=True,
        )

        disabled_user = User.objects.create_user(
            phone_e164="+6591111113",
            role=UserRole.RECEIVER,
            is_active=True,
        )
        ReceiverProfile.objects.create(
            user=disabled_user,
            display_name="Location Off",
            latitude=LAT,
            longitude=LNG,
            browse_radius_km=5.0,
            location_services_enabled=False,
        )

        client = auth_client(api_client, restaurant_user)
        now = timezone.now()
        response = client.post(
            reverse("restaurant_donations:restaurant-donations"),
            {
                "name": "Chicken Rice",
                "category": "RICE",
                "quantity": 5,
                "pickup_start": now.isoformat(),
                "pickup_end": (now + timedelta(hours=2)).isoformat(),
                "recurrence_type": "NONE",
            },
            format="json",
        )
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["estimated_reach"] == 1

        food_id = data["id"]
        nearby_notes = Notification.objects.filter(
            user=nearby_user,
            type="NEW_FOOD_NEARBY",
        )
        assert nearby_notes.count() == 1
        note = nearby_notes.get()
        assert note.title == "New food near you"
        assert "Chicken Rice" in note.body
        assert note.payload["food_id"] == food_id
        assert note.payload["restaurant_id"] == str(restaurant_user.restaurant_profile.id)

        assert not Notification.objects.filter(user=far_user).exists()
        assert not Notification.objects.filter(user=disabled_user).exists()


class TestRestaurantProfile:
    def test_profile_and_approval_status(self, api_client, restaurant_user):
        client = auth_client(api_client, restaurant_user)

        profile = client.get(reverse("restaurant_donations:restaurant-profile"))
        assert profile.status_code == 200
        data = profile.json()["data"]
        assert data["name"] == "Tian Tian Hainanese"
        assert data["initials"] == "TT"
        assert data["people_fed"] == 0
        assert data["claim_rate_display"] == "—"
        assert data["rating"] is None
        assert data["hub"]["reviews_available"] is False
        assert "member_since" in data

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
                "cuisine": "Hainanese · Chinese",
                "opens_at": "10:00:00",
                "closes_at": "21:00:00",
                "open_days": [0, 1, 2, 3, 4, 5, 6],
            },
            format="json",
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["contact_name"] == "New Manager"
        assert data["about"] == "Family-run since 1990"
        assert data["cuisine"] == "Hainanese · Chinese"
        assert data["opens_at"] == "10:00:00"
        assert data["closes_at"] == "21:00:00"
        assert data["open_days"] == [0, 1, 2, 3, 4, 5, 6]
        assert "10:00 AM" in data["opening_hours"]
        assert data["uen_verified"] is True

    def test_upload_restaurant_photo(self, api_client, restaurant_user):
        from django.core.files.uploadedfile import SimpleUploadedFile

        client = auth_client(api_client, restaurant_user)
        photo = SimpleUploadedFile(
            "storefront.jpg",
            b"\xff\xd8\xff\xe0" + b"0" * 64,
            content_type="image/jpeg",
        )
        response = client.patch(
            reverse("restaurant_donations:restaurant-profile"),
            {"photo": photo},
            format="multipart",
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["photo_url"] is not None
        assert "/media/restaurants/" in data["photo_url"]

    def test_public_restaurant_page(self, api_client, restaurant_user):
        restaurant = restaurant_user.restaurant_profile
        restaurant.about = "Family-run since 1987"
        restaurant.is_verified = True
        restaurant.save(update_fields=["about", "is_verified"])
        response = api_client.get(
            reverse("public-restaurant", kwargs={"restaurant_id": restaurant.id})
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["name"] == "Tian Tian Hainanese"
        assert data["area_label"] == "Joo Chiat"
        assert data["about"] == "Family-run since 1987"
        assert data["verified_label"] == "Verified partner"
        assert "impact" in data
        assert data["impact"]["people_fed"] == 0
        assert data["impact"]["donations_count"] == 0
        assert "available_meals" in data


class TestRestaurantNotificationSettings:
    def test_get_and_patch_settings(self, api_client, restaurant_user):
        client = auth_client(api_client, restaurant_user)
        url = reverse("restaurant_accounts:restaurant-notification-settings")

        response = client.get(url)
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["push_enabled"] is True
        assert data["alert_new_claim"] is True
        assert data["alert_no_show"] is True
        assert data["email_enabled"] is False

        response = client.patch(
            url,
            {
                "push_enabled": False,
                "alert_no_show": False,
                "email_enabled": True,
            },
            format="json",
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["push_enabled"] is False
        assert data["alert_no_show"] is False
        assert data["email_enabled"] is True
        assert data["alert_new_claim"] is True


class TestRestaurantAccount:
    def test_data_export_download(self, api_client, restaurant_user):
        client = auth_client(api_client, restaurant_user)
        response = client.get(
            reverse("restaurant_accounts:restaurant-data-export-download")
        )
        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"
        assert response.content[:4] == b"%PDF"

    def test_request_data_export(self, api_client, restaurant_user):
        client = auth_client(api_client, restaurant_user)
        response = client.post(
            reverse("restaurant_accounts:restaurant-data-export")
        )
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["format"] == "pdf"
        assert data["status"] == "COMPLETED"
        assert data["delivery"] == "email"
        assert data["eta_hours"] == 48
        assert data["email"] == "contact@restaurant.sg"
        assert data["email_sent"] is True
        assert "download_url" in data
        assert "Sponsored-order" in " ".join(data["includes"])

    def test_delete_account(self, api_client, restaurant_user):
        from apps.accounts.models import RestaurantLegalRetention, User
        from apps.common.choices import ListStatus
        from apps.donations.models import FoodItem

        now = timezone.now()
        FoodItem.objects.create(
            restaurant=restaurant_user.restaurant_profile,
            name="Chicken Rice",
            category="RICE",
            quantity_original=5,
            quantity_available=5,
            pickup_start=now,
            pickup_end=now + timedelta(hours=2),
            list_status=ListStatus.ACTIVE,
        )

        client = auth_client(api_client, restaurant_user)
        user_id = restaurant_user.id
        uen = restaurant_user.restaurant_profile.uen
        response = client.post(
            reverse("restaurant_accounts:restaurant-account-delete"),
            {"confirmation": "DELETE"},
            format="json",
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["deleted"] is True
        assert data["active_donations_deactivated"] == 1
        assert data["retention"]["uen_contact_days"] == 90
        assert data["retention"]["payout_years"] == 7
        assert not User.objects.filter(id=user_id).exists()
        assert RestaurantLegalRetention.objects.filter(uen=uen).exists()

    def test_delete_account_requires_confirmation(self, api_client, restaurant_user):
        client = auth_client(api_client, restaurant_user)
        response = client.post(
            reverse("restaurant_accounts:restaurant-account-delete"),
            {"confirmation": "please"},
            format="json",
        )
        assert response.status_code == 400
