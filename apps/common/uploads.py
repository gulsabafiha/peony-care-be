from __future__ import annotations

import uuid

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
    if not photo_url or not photo_url.startswith(settings.MEDIA_URL):
        return

    relative_path = photo_url.removeprefix(settings.MEDIA_URL)
    if default_storage.exists(relative_path):
        default_storage.delete(relative_path)
