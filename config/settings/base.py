from datetime import timedelta
from pathlib import Path

import dj_database_url
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config("DJANGO_SECRET_KEY", default="django-insecure-dev-only-change-me")
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = [
    host.strip()
    for host in config("ALLOWED_HOSTS", default="localhost,127.0.0.1").split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "corsheaders",
    "apps.accounts",
    "apps.donations",
    "apps.claims",
    "apps.donors",
    "apps.notifications",
    "apps.common",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": dj_database_url.parse(
        config("DATABASE_URL", default="postgres://peony:peony@localhost:5432/peony")
    )
}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Singapore"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.common.exceptions.custom_exception_handler",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

# Udufood business config
MAX_CLAIM_DISTANCE_M = config("MAX_CLAIM_DISTANCE_M", default=500, cast=int)
DAILY_CLAIM_LIMIT = config("DAILY_CLAIM_LIMIT", default=1, cast=int)
DEFAULT_BROWSE_RADIUS_KM = config("DEFAULT_BROWSE_RADIUS_KM", default=5, cast=int)
MAX_PROFILE_PHOTO_BYTES = config("MAX_PROFILE_PHOTO_BYTES", default=5 * 1024 * 1024, cast=int)

# AWS / OTP (configured per environment)
AWS_ACCESS_KEY_ID = config("AWS_ACCESS_KEY_ID", default="")
AWS_SECRET_ACCESS_KEY = config("AWS_SECRET_ACCESS_KEY", default="")
AWS_STORAGE_BUCKET_NAME = config("AWS_STORAGE_BUCKET_NAME", default="")
AWS_S3_REGION_NAME = config("AWS_S3_REGION_NAME", default="ap-southeast-1")
OTP_PROVIDER = config("OTP_PROVIDER", default="console")
# Optional alphanumeric sender ID (country-dependent; often unused in SNS sandbox)
OTP_SMS_SENDER_ID = config("OTP_SMS_SENDER_ID", default="")
OTP_EXPIRY_MINUTES = config("OTP_EXPIRY_MINUTES", default=1, cast=int)
OTP_MAX_ATTEMPTS = config("OTP_MAX_ATTEMPTS", default=5, cast=int)
OTP_RESEND_COOLDOWN_SECONDS = config("OTP_RESEND_COOLDOWN_SECONDS", default=60, cast=int)
# Twilio Verify (when OTP_PROVIDER=twilio)
TWILIO_ACCOUNT_SID = config("TWILIO_ACCOUNT_SID", default="")
TWILIO_AUTH_TOKEN = config("TWILIO_AUTH_TOKEN", default="")
TWILIO_VERIFY_SERVICE_SID = config("TWILIO_VERIFY_SERVICE_SID", default="")
TWILIO_VERIFY_CODE_LENGTH = config("TWILIO_VERIFY_CODE_LENGTH", default=4, cast=int)
# Temporary: accept fixed bypass OTP while Twilio Verify is blocked (set False when Twilio works)
OTP_ALLOW_DEV_BYPASS = config("OTP_ALLOW_DEV_BYPASS", default=True, cast=bool)
OTP_DEV_BYPASS_CODE = config("OTP_DEV_BYPASS_CODE", default="0000")
# Play Store reviewers: comma-separated E.164 phones; fixed OTP; SMS skipped
PLAY_STORE_REVIEW_PHONES = config(
    "PLAY_STORE_REVIEW_PHONES",
    default="+6590000001,+6590000002",
)
PLAY_STORE_REVIEW_OTP = config("PLAY_STORE_REVIEW_OTP", default="1234")
REGISTRATION_TOKEN_MAX_AGE_SECONDS = config(
    "REGISTRATION_TOKEN_MAX_AGE_SECONDS", default=1800, cast=int
)

# PayNow (money donations)
PAYNOW_UEN = config("PAYNOW_UEN", default="")
PAYNOW_ACCOUNT_NAME = config("PAYNOW_ACCOUNT_NAME", default="Udufood Ltd")

# Email (console backend by default — configure SMTP in production)
EMAIL_BACKEND = config(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="support@udufood.com")
DATA_EXPORT_EMAIL_ETA_HOURS = config("DATA_EXPORT_EMAIL_ETA_HOURS", default=48, cast=int)

# Restaurant account deletion retention (PDPA / ACRA)
RESTAURANT_UEN_RETENTION_DAYS = config("RESTAURANT_UEN_RETENTION_DAYS", default=90, cast=int)
RESTAURANT_PAYOUT_RETENTION_YEARS = config(
    "RESTAURANT_PAYOUT_RETENTION_YEARS", default=7, cast=int
)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "[{levelname}] {asctime} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "apps": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Udufood API",
    "DESCRIPTION": "Backend API for the Udufood food-share application.",
    "VERSION": "1.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
        "persistAuthorization": True,
        "displayOperationId": True,
    },
    "POSTPROCESSING_HOOKS": [
        "drf_spectacular.hooks.postprocess_schema_enums",
        "apps.common.schema.add_standard_error_response",
    ],
    "APPEND_COMPONENTS": {
        "securitySchemes": {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": (
                    "Paste only the JWT access token. Do not include 'Bearer'; "
                    "Swagger UI adds it automatically."
                ),
            },
            "RegistrationToken": {
                "type": "apiKey",
                "in": "header",
                "name": "Registration-Token",
            },
        }
    },
    "SECURITY": [{"BearerAuth": []}],
}
