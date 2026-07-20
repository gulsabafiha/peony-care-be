from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403

DEBUG = False

CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in config("CORS_ALLOWED_ORIGINS", default="").split(",")  # noqa: F405
    if origin.strip()
]

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in config("CSRF_TRUSTED_ORIGINS", default="").split(",")  # noqa: F405
    if origin.strip()
]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# Set SECURE_SSL_REDIRECT=False when serving admin/API over plain HTTP (e.g. EC2 :8000).
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)  # noqa: F405
SESSION_COOKIE_SECURE = SECURE_SSL_REDIRECT
CSRF_COOKIE_SECURE = SECURE_SSL_REDIRECT

if SECURE_SSL_REDIRECT:
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
else:
    SECURE_HSTS_SECONDS = 0

# Media uploads (menu / food / profile photos) go to S3 in production only.
if not AWS_STORAGE_BUCKET_NAME:  # noqa: F405
    raise ImproperlyConfigured(
        "AWS_STORAGE_BUCKET_NAME is required when using production settings."
    )
if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:  # noqa: F405
    raise ImproperlyConfigured(
        "AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are required when using "
        "production settings."
    )

INSTALLED_APPS = [*INSTALLED_APPS, "storages"]  # noqa: F405

AWS_S3_CUSTOM_DOMAIN = config(  # noqa: F405
    "AWS_S3_CUSTOM_DOMAIN",
    default=f"{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com",  # noqa: F405
)
AWS_DEFAULT_ACL = None
AWS_QUERYSTRING_AUTH = False
# Filenames already include a UUID (see apps.common.uploads), so skip the
# pre-upload HeadObject "exists" check. That call often 403s when IAM only
# grants PutObject, which surfaces as a 500 on menu/food/profile uploads.
AWS_S3_FILE_OVERWRITE = True
AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=86400"}
AWS_S3_SIGNATURE_VERSION = "s3v4"

MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/"
STORAGES = {
    **STORAGES,  # noqa: F405
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": AWS_STORAGE_BUCKET_NAME,  # noqa: F405
            "region_name": AWS_S3_REGION_NAME,  # noqa: F405
            "default_acl": None,
            "querystring_auth": False,
            "file_overwrite": True,
            "object_parameters": {"CacheControl": "max-age=86400"},
            "signature_version": "s3v4",
            "custom_domain": AWS_S3_CUSTOM_DOMAIN,
        },
    },
}
