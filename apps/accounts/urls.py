from django.urls import path

from apps.accounts.views import (
    DonorRegisterView,
    LogoutView,
    OtpSendView,
    OtpVerifyView,
    ReceiverRegisterView,
    RestaurantRegisterView,
    TokenRefreshView,
)

urlpatterns = [
    path("otp/send/", OtpSendView.as_view(), name="auth-otp-send"),
    path("otp/verify/", OtpVerifyView.as_view(), name="auth-otp-verify"),
    path("register/receiver/", ReceiverRegisterView.as_view(), name="auth-register-receiver"),
    path("register/restaurant/", RestaurantRegisterView.as_view(), name="auth-register-restaurant"),
    path("register/donor/", DonorRegisterView.as_view(), name="auth-register-donor"),
    path("token/refresh/", TokenRefreshView.as_view(), name="auth-token-refresh"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
]
