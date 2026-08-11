import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.common.choices import UserRole
from apps.notifications.models import Notification

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def receiver_user():
    return User.objects.create_user(
        phone_e164="+6591000001",
        role=UserRole.RECEIVER,
        is_active=True,
    )


def auth_client(api_client, user):
    token = str(RefreshToken.for_user(user).access_token)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return api_client


class TestNotificationInbox:
    def test_list_mark_read_and_mark_all(self, api_client, receiver_user):
        unread = Notification.objects.create(
            user=receiver_user,
            type="NEW_FOOD_NEARBY",
            title="New food near you",
            body="Restaurant just posted Chicken Rice nearby.",
            payload={"food_id": "11111111-1111-1111-1111-111111111111", "distance_km": 0.5},
        )
        Notification.objects.create(
            user=receiver_user,
            type="CLAIM_CONFIRMED",
            title="Meal claimed!",
            body="You claimed Chicken Rice.",
            payload={"claim_id": "22222222-2222-2222-2222-222222222222"},
        )
        other = User.objects.create_user(
            phone_e164="+6591000002",
            role=UserRole.RECEIVER,
            is_active=True,
        )
        Notification.objects.create(
            user=other,
            type="NEW_FOOD_NEARBY",
            title="Hidden",
            body="Should not appear",
        )

        client = auth_client(api_client, receiver_user)

        list_response = client.get(reverse("notifications-list"))
        assert list_response.status_code == 200
        payload = list_response.json()["data"]
        assert payload["unread_count"] == 2
        assert len(payload["items"]) == 2
        assert payload["items"][0]["type"] in {"NEW_FOOD_NEARBY", "CLAIM_CONFIRMED"}
        assert payload["items"][0]["is_read"] is False
        assert "payload" in payload["items"][0]

        unread_only = client.get(reverse("notifications-list"), {"unread_only": "true"})
        assert unread_only.status_code == 200
        assert len(unread_only.json()["data"]["items"]) == 2

        mark_one = client.post(
            reverse("notifications-mark-read", kwargs={"notification_id": unread.id})
        )
        assert mark_one.status_code == 200
        assert mark_one.json()["data"]["is_read"] is True
        assert mark_one.json()["data"]["read_at"] is not None

        count_response = client.get(reverse("notifications-unread-count"))
        assert count_response.json()["data"]["unread_count"] == 1

        mark_all = client.post(reverse("notifications-read-all"))
        assert mark_all.status_code == 200
        assert mark_all.json()["data"]["marked_read"] == 1
        assert mark_all.json()["data"]["unread_count"] == 0

        final_count = client.get(reverse("notifications-unread-count"))
        assert final_count.json()["data"]["unread_count"] == 0

    def test_mark_read_not_found(self, api_client, receiver_user):
        client = auth_client(api_client, receiver_user)
        response = client.post(
            reverse(
                "notifications-mark-read",
                kwargs={"notification_id": "33333333-3333-3333-3333-333333333333"},
            )
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOTIFICATION_NOT_FOUND"
