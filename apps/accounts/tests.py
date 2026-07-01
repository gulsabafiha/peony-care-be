from datetime import timedelta
from unittest.mock import patch

import pytest
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import OtpChallenge, RefreshToken, User
from apps.accounts.services import _hash_value
from apps.common.choices import OtpPurpose, UserRole

pytestmark = pytest.mark.django_db

PHONE = "+6591234567"
OTP_CODE = "1234"


@pytest.fixture
def api_client():
    return APIClient()


def _create_otp(phone: str = PHONE, purpose: str = OtpPurpose.REGISTER, code: str = OTP_CODE):
    return OtpChallenge.objects.create(
        phone_e164=phone,
        code_hash=_hash_value(code),
        purpose=purpose,
        expires_at=timezone.now() + timedelta(minutes=settings.OTP_EXPIRY_MINUTES),
    )


class TestOtpSend:
    @patch("apps.accounts.services._generate_otp_code", return_value=OTP_CODE)
    def test_send_register_otp(self, _mock_code, api_client):
        response = api_client.post(
            reverse("auth-otp-send"),
            {"phone": PHONE, "purpose": OtpPurpose.REGISTER},
            format="json",
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        assert response.json()["data"]["phone"] == PHONE
        assert OtpChallenge.objects.filter(phone_e164=PHONE).exists()

    @patch("apps.accounts.services._generate_otp_code", return_value=OTP_CODE)
    def test_send_register_otp_normalizes_spaced_phone(self, _mock_code, api_client):
        response = api_client.post(
            reverse("auth-otp-send"),
            {"phone": "+65 9123 4567", "purpose": OtpPurpose.REGISTER},
            format="json",
        )
        assert response.status_code == 200
        assert response.json()["data"]["phone"] == PHONE
        assert OtpChallenge.objects.filter(phone_e164=PHONE).exists()

    def test_send_register_rejects_already_registered_spaced_phone(self, api_client):
        from apps.accounts.models import ReceiverProfile

        user = User.objects.create_user(
            phone_e164=PHONE,
            role=UserRole.RECEIVER,
            is_active=True,
        )
        ReceiverProfile.objects.create(
            user=user,
            display_name="Sarah",
            latitude=1.3521,
            longitude=103.8198,
        )

        response = api_client.post(
            reverse("auth-otp-send"),
            {"phone": "+65 9123 4567", "purpose": OtpPurpose.REGISTER},
            format="json",
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "ALREADY_REGISTERED"

    def test_send_register_rejects_legacy_spaced_phone_in_database(self, api_client):
        from apps.accounts.models import ReceiverProfile

        user = User(phone_e164="+65 9123 4567", role=UserRole.RECEIVER, is_active=True)
        user.set_unusable_password()
        user.save()
        ReceiverProfile.objects.create(
            user=user,
            display_name="Sarah",
            latitude=1.3521,
            longitude=103.8198,
        )

        response = api_client.post(
            reverse("auth-otp-send"),
            {"phone": PHONE, "purpose": OtpPurpose.REGISTER},
            format="json",
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "ALREADY_REGISTERED"

    def test_send_login_otp_finds_legacy_spaced_phone_in_database(self, api_client):
        from apps.accounts.models import ReceiverProfile

        user = User(phone_e164="+65 9123 4567", role=UserRole.RECEIVER, is_active=True)
        user.set_unusable_password()
        user.save()
        ReceiverProfile.objects.create(
            user=user,
            display_name="Sarah",
            latitude=1.3521,
            longitude=103.8198,
        )

        with patch("apps.accounts.services._generate_otp_code", return_value=OTP_CODE):
            response = api_client.post(
                reverse("auth-otp-send"),
                {"phone": PHONE, "purpose": OtpPurpose.LOGIN},
                format="json",
            )

        assert response.status_code == 200
        assert response.json()["data"]["phone"] == PHONE
        user.refresh_from_db()
        assert user.phone_e164 == PHONE

    def test_send_login_otp_requires_existing_user(self, api_client):
        response = api_client.post(
            reverse("auth-otp-send"),
            {"phone": PHONE, "purpose": OtpPurpose.LOGIN},
            format="json",
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "USER_NOT_FOUND"


class TestUserManager:
    def test_regular_user_has_unusable_password(self):
        user = User.objects.create_user(
            phone_e164=PHONE,
            role=UserRole.RECEIVER,
        )

        assert user.has_usable_password() is False

    def test_create_user_normalizes_spaced_phone(self):
        user = User.objects.create_user(
            phone_e164="+65 9123 4567",
            role=UserRole.RECEIVER,
        )

        assert user.phone_e164 == PHONE

    def test_superuser_password_is_usable(self):
        user = User.objects.create_superuser(
            phone_e164="+6598765432",
            password="StrongTestPass123!",
        )

        assert user.is_staff is True
        assert user.is_superuser is True
        assert user.is_active is True
        assert user.check_password("StrongTestPass123!") is True


class TestOtpVerify:
    @patch("apps.accounts.services._generate_otp_code", return_value=OTP_CODE)
    def test_verify_register_returns_registration_token(self, _mock_code, api_client):
        api_client.post(
            reverse("auth-otp-send"),
            {"phone": PHONE, "purpose": OtpPurpose.REGISTER},
            format="json",
        )
        response = api_client.post(
            reverse("auth-otp-verify"),
            {"phone": PHONE, "code": OTP_CODE},
            format="json",
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert "registration_token" in data
        assert data["phone"] == PHONE

    @patch("apps.accounts.services._generate_otp_code", return_value=OTP_CODE)
    def test_verify_login_returns_jwt(self, _mock_code, api_client):
        user = User.objects.create_user(
            phone_e164=PHONE,
            role=UserRole.RECEIVER,
            is_active=True,
        )
        from apps.accounts.models import ReceiverProfile

        ReceiverProfile.objects.create(
            user=user,
            display_name="Sarah",
            latitude=1.3521,
            longitude=103.8198,
        )

        api_client.post(
            reverse("auth-otp-send"),
            {"phone": PHONE, "purpose": OtpPurpose.LOGIN},
            format="json",
        )
        response = api_client.post(
            reverse("auth-otp-verify"),
            {"phone": PHONE, "code": OTP_CODE},
            format="json",
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert "access" in data
        assert "refresh" in data
        assert data["user"]["id"] == str(user.id)


class TestRegistration:
    def _registration_token(self, api_client) -> str:
        with patch("apps.accounts.services._generate_otp_code", return_value=OTP_CODE):
            api_client.post(
                reverse("auth-otp-send"),
                {"phone": PHONE, "purpose": OtpPurpose.REGISTER},
                format="json",
            )
            response = api_client.post(
                reverse("auth-otp-verify"),
                {"phone": PHONE, "code": OTP_CODE},
                format="json",
            )
        return response.json()["data"]["registration_token"]

    def test_register_receiver(self, api_client):
        token = self._registration_token(api_client)
        response = api_client.post(
            reverse("auth-register-receiver"),
            {
                "display_name": "Sarah Mun",
                "latitude": 1.3521,
                "longitude": 103.8198,
            },
            format="json",
            HTTP_REGISTRATION_TOKEN=token,
        )
        assert response.status_code == 201
        data = response.json()["data"]
        assert "access" in data
        user = User.objects.get(phone_e164=PHONE)
        assert user.role == UserRole.RECEIVER
        assert user.is_active is True
        assert user.receiver_profile.display_name == "Sarah Mun"
        assert float(user.receiver_profile.latitude) == 1.3521
        assert float(user.receiver_profile.longitude) == 103.8198
        assert user.receiver_profile.browse_radius_km == 5.0

    def test_register_restaurant(self, api_client):
        token = self._registration_token(api_client)
        response = api_client.post(
            reverse("auth-register-restaurant"),
            {
                "restaurant_name": "Tian Tian Hainanese",
                "uen": "200912345A",
                "address": "443 Joo Chiat Rd, Singapore 427656",
                "contact_name": "Manager",
                "contact_email": "contact@restaurant.sg",
            },
            format="json",
            HTTP_REGISTRATION_TOKEN=token,
        )
        assert response.status_code == 201
        user = User.objects.get(phone_e164=PHONE)
        assert user.restaurant_profile.name == "Tian Tian Hainanese"
        assert float(user.restaurant_profile.latitude) == 1.3521
        assert float(user.restaurant_profile.longitude) == 103.8198
        assert user.restaurant_profile.is_approved is True
        assert user.restaurant_profile.approved_at is not None

    def test_register_restaurant_with_map_pin(self, api_client):
        token = self._registration_token(api_client)
        response = api_client.post(
            reverse("auth-register-restaurant"),
            {
                "restaurant_name": "Tian Tian Hainanese",
                "uen": "200912345B",
                "address": "443 Joo Chiat Rd, Singapore 427656",
                "contact_name": "Manager",
                "latitude": 1.3012345,
                "longitude": 103.8587654,
            },
            format="json",
            HTTP_REGISTRATION_TOKEN=token,
        )
        assert response.status_code == 201
        user = User.objects.get(phone_e164=PHONE)
        assert float(user.restaurant_profile.latitude) == 1.3012345
        assert float(user.restaurant_profile.longitude) == 103.8587654

    def test_register_restaurant_rejects_partial_map_pin(self, api_client):
        token = self._registration_token(api_client)
        response = api_client.post(
            reverse("auth-register-restaurant"),
            {
                "restaurant_name": "Tian Tian Hainanese",
                "uen": "200912345C",
                "address": "443 Joo Chiat Rd, Singapore 427656",
                "contact_name": "Manager",
                "latitude": 1.3012345,
            },
            format="json",
            HTTP_REGISTRATION_TOKEN=token,
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_register_donor(self, api_client):
        token = self._registration_token(api_client)
        response = api_client.post(
            reverse("auth-register-donor"),
            {"display_name": "James Tan", "contact_email": "james@example.com"},
            format="json",
            HTTP_REGISTRATION_TOKEN=token,
        )
        assert response.status_code == 201
        data = response.json()["data"]
        assert "access" in data
        assert "refresh" in data
        user = User.objects.get(phone_e164=PHONE)
        assert user.role == UserRole.DONOR
        assert user.is_active is True
        assert user.donor_profile.display_name == "James Tan"
        assert user.donor_profile.contact_email == "james@example.com"

    def test_register_requires_token(self, api_client):
        response = api_client.post(
            reverse("auth-register-receiver"),
            {"display_name": "Sarah Mun"},
            format="json",
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "MISSING_REGISTRATION_TOKEN"


class TestTokenLifecycle:
    @patch("apps.accounts.services._generate_otp_code", return_value=OTP_CODE)
    def test_refresh_and_logout(self, _mock_code, api_client):
        token = self._registration_token(api_client)
        register_response = api_client.post(
            reverse("auth-register-donor"),
            {"display_name": "John Tan", "contact_email": "john@example.com"},
            format="json",
            HTTP_REGISTRATION_TOKEN=token,
        )
        refresh_token = register_response.json()["data"]["refresh"]

        refresh_response = api_client.post(
            reverse("auth-token-refresh"),
            {"refresh": refresh_token},
            format="json",
        )
        assert refresh_response.status_code == 200
        assert "access" in refresh_response.json()["data"]

        logout_response = api_client.post(
            reverse("auth-logout"),
            {"refresh": refresh_token},
            format="json",
        )
        assert logout_response.status_code == 200
        assert RefreshToken.objects.filter(revoked_at__isnull=False).exists()

    def _registration_token(self, api_client) -> str:
        with patch("apps.accounts.services._generate_otp_code", return_value=OTP_CODE):
            api_client.post(
                reverse("auth-otp-send"),
                {"phone": PHONE, "purpose": OtpPurpose.REGISTER},
                format="json",
            )
            response = api_client.post(
                reverse("auth-otp-verify"),
                {"phone": PHONE, "code": OTP_CODE},
                format="json",
            )
        return response.json()["data"]["registration_token"]


class TestSwaggerSchema:
    def test_schema_endpoint_available(self, api_client):
        response = api_client.get(reverse("schema"))
        assert response.status_code == 200
        assert b"Peony Care API" in response.content
        assert b"/api/v1/auth/otp/send/" in response.content
