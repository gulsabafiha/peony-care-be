from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.common.choices import UserRole
from apps.common.timezone_utils import SGT, today_sgt
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


def _create_notification(user, *, title="Alert", created_at=None, **kwargs):
    notification = Notification.objects.create(
        user=user,
        type=kwargs.get("type", "NEW_FOOD_NEARBY"),
        title=title,
        body=kwargs.get("body", "Body"),
        payload=kwargs.get("payload", {}),
    )
    if created_at is not None:
        Notification.objects.filter(id=notification.id).update(created_at=created_at)
        notification.refresh_from_db()
    return notification


class TestNotificationInbox:
    def test_list_grouped_by_date_with_pagination(self, api_client, receiver_user):
        today = today_sgt()
        today_noon = timezone.datetime(today.year, today.month, today.day, 12, 0, tzinfo=SGT)
        yesterday_noon = today_noon - timedelta(days=1)

        newer = _create_notification(
            receiver_user,
            title="Today alert",
            created_at=today_noon,
            payload={"food_id": "11111111-1111-1111-1111-111111111111"},
        )
        _create_notification(
            receiver_user,
            title="Yesterday alert",
            type="CLAIM_CONFIRMED",
            created_at=yesterday_noon,
        )
        other = User.objects.create_user(
            phone_e164="+6591000002",
            role=UserRole.RECEIVER,
            is_active=True,
        )
        _create_notification(other, title="Hidden")

        client = auth_client(api_client, receiver_user)
        list_response = client.get(
            reverse("notifications-list"),
            {"page": 1, "page_size": 20},
        )
        assert list_response.status_code == 200
        payload = list_response.json()["data"]
        assert payload["unread_count"] == 2
        assert payload["pagination"]["page"] == 1
        assert payload["pagination"]["page_size"] == 20
        assert payload["pagination"]["total_count"] == 2
        assert payload["pagination"]["total_pages"] == 1
        assert payload["pagination"]["has_next"] is False
        assert payload["pagination"]["has_previous"] is False

        assert len(payload["groups"]) == 2
        assert payload["groups"][0]["label"] == "Today"
        assert payload["groups"][0]["date"] == today.isoformat()
        assert payload["groups"][0]["count"] == 1
        assert payload["groups"][0]["items"][0]["title"] == "Today alert"
        assert payload["groups"][1]["label"] == "Yesterday"
        assert payload["groups"][1]["items"][0]["title"] == "Yesterday alert"

        unread_only = client.get(
            reverse("notifications-list"),
            {"unread_only": "true", "page_size": 1},
        )
        assert unread_only.status_code == 200
        unread_payload = unread_only.json()["data"]
        assert unread_payload["pagination"]["total_count"] == 2
        assert unread_payload["pagination"]["total_pages"] == 2
        assert unread_payload["pagination"]["has_next"] is True
        assert sum(group["count"] for group in unread_payload["groups"]) == 1

        page_two = client.get(
            reverse("notifications-list"),
            {"unread_only": "true", "page": 2, "page_size": 1},
        )
        assert page_two.status_code == 200
        page_two_payload = page_two.json()["data"]
        assert page_two_payload["pagination"]["page"] == 2
        assert page_two_payload["pagination"]["has_previous"] is True
        assert page_two_payload["pagination"]["has_next"] is False

        mark_one = client.post(
            reverse("notifications-mark-read", kwargs={"notification_id": newer.id})
        )
        assert mark_one.status_code == 200
        assert mark_one.json()["data"]["is_read"] is True

        count_response = client.get(reverse("notifications-unread-count"))
        assert count_response.json()["data"]["unread_count"] == 1

        mark_all = client.post(reverse("notifications-read-all"))
        assert mark_all.status_code == 200
        assert mark_all.json()["data"]["marked_read"] == 1
        assert mark_all.json()["data"]["unread_count"] == 0

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
