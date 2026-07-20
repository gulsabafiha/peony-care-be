from __future__ import annotations

import uuid
from urllib.parse import unquote, urlparse

from django.conf import settings
from django.core.files.storage import default_storage

from apps.common.exceptions import PeonyAPIException

ALLOWED_PROFILE_PHOTO_CONTENT_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


def _save_profile_photo(prefix: str, owner_id: str, uploaded_file) -> str:
    content_type = getattr(uploaded_file, "content_type", "") or ""
    extension = ALLOWED_PROFILE_PHOTO_CONTENT_TYPES.get(content_type)
    if extension is None:
        raise PeonyAPIException(
            code="INVALID_IMAGE",
            message="Profile photo must be a JPEG, PNG, or WebP image.",
            http_status=400,
        )

    if uploaded_file.size > settings.MAX_PROFILE_PHOTO_BYTES:
        max_mb = settings.MAX_PROFILE_PHOTO_BYTES // (1024 * 1024)
        raise PeonyAPIException(
            code="IMAGE_TOO_LARGE",
            message=f"Profile photo must be {max_mb}MB or smaller.",
            http_status=400,
        )

    filename = f"{prefix}/{owner_id}/{uuid.uuid4()}.{extension}"
    saved_path = default_storage.save(filename, uploaded_file)
    return default_storage.url(saved_path)


def save_receiver_profile_photo(user_id: str, uploaded_file) -> str:
    return _save_profile_photo("receivers", user_id, uploaded_file)


def save_restaurant_profile_photo(restaurant_id: str, uploaded_file) -> str:
    return _save_profile_photo("restaurants", restaurant_id, uploaded_file)


def save_food_item_photo(restaurant_id: str, uploaded_file) -> str:
    return _save_profile_photo("foods", restaurant_id, uploaded_file)


def save_menu_photo(restaurant_id: str, uploaded_file) -> str:
    return _save_profile_photo("menu-photos", restaurant_id, uploaded_file)


def delete_stored_photo(photo_url: str) -> None:
    if not photo_url:
        return

    media_url = settings.MEDIA_URL
    if photo_url.startswith(media_url):
        relative_path = photo_url.removeprefix(media_url).split("?", 1)[0]
    else:
        # Support absolute S3 URLs when MEDIA_URL is local (or vice versa).
        path = unquote(urlparse(photo_url).path.lstrip("/"))
        bucket = getattr(settings, "AWS_STORAGE_BUCKET_NAME", "") or ""
        if bucket and path.startswith(f"{bucket}/"):
            path = path[len(bucket) + 1 :]
        known_prefixes = ("receivers/", "restaurants/", "foods/", "menu-photos/")
        if not path.startswith(known_prefixes):
            return
        relative_path = path

    if relative_path and default_storage.exists(relative_path):
        default_storage.delete(relative_path)
