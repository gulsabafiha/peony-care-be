from __future__ import annotations

from django.db import transaction

from apps.accounts.models import User
from apps.common.exceptions import PeonyAPIException
from apps.common.uploads import delete_stored_photo, save_menu_photo
from apps.donations.models import MenuPhoto
from apps.donations.restaurant_services import get_restaurant_profile

MAX_MENU_PHOTOS = 10


def _absolute_photo_url(request, photo_url: str | None) -> str | None:
    if not photo_url:
        return None
    if photo_url.startswith("http://") or photo_url.startswith("https://"):
        return photo_url
    if request is None:
        return photo_url
    return request.build_absolute_uri(photo_url)


def _serialize_photo(photo: MenuPhoto, request=None) -> dict:
    return {
        "id": str(photo.id),
        "photo_url": _absolute_photo_url(request, photo.photo_url),
        "sort_order": photo.sort_order,
        "position": photo.sort_order,
        "created_at": photo.created_at.isoformat(),
    }


def _photos_queryset(restaurant):
    return MenuPhoto.objects.filter(restaurant=restaurant).order_by("sort_order", "created_at")


def _renumber_photos(restaurant) -> None:
    photos = list(_photos_queryset(restaurant))
    for index, photo in enumerate(photos, start=1):
        if photo.sort_order != index:
            photo.sort_order = index
            photo.save(update_fields=["sort_order"])


def list_menu_photos(user: User, request=None) -> dict:
    restaurant = get_restaurant_profile(user)
    photos = list(_photos_queryset(restaurant))
    serialized = [_serialize_photo(photo, request=request) for photo in photos]
    uploaded_count = len(serialized)
    slots_left = max(MAX_MENU_PHOTOS - uploaded_count, 0)
    return {
        "max_photos": MAX_MENU_PHOTOS,
        "uploaded_count": uploaded_count,
        "slots_left": slots_left,
        "is_empty": uploaded_count == 0,
        "photos": serialized,
        "donor_preview": {
            "total": uploaded_count,
            "photos": serialized,
        },
        "reorder_hint": (
            "Long-press a photo to reorder. Photo #1 is the first one donors see."
        ),
        "counter_label": f"{uploaded_count} uploaded · max {MAX_MENU_PHOTOS}",
        "add_slot_label": (
            None
            if slots_left <= 0
            else f"Add photo / {slots_left} slot{'s' if slots_left != 1 else ''} left"
        ),
    }


@transaction.atomic
def create_menu_photos(user: User, files: list, request=None) -> dict:
    restaurant = get_restaurant_profile(user)
    if not files:
        raise PeonyAPIException(
            code="PHOTO_REQUIRED",
            message="At least one photo file is required.",
            http_status=400,
        )

    current_count = _photos_queryset(restaurant).count()
    slots_left = MAX_MENU_PHOTOS - current_count
    if slots_left <= 0:
        raise PeonyAPIException(
            code="MENU_PHOTO_LIMIT",
            message=f"Maximum of {MAX_MENU_PHOTOS} menu photos allowed.",
            http_status=400,
        )
    if len(files) > slots_left:
        raise PeonyAPIException(
            code="MENU_PHOTO_LIMIT",
            message=(
                f"Only {slots_left} slot{'s' if slots_left != 1 else ''} left "
                f"(max {MAX_MENU_PHOTOS})."
            ),
            http_status=400,
        )

    next_order = current_count + 1
    created = []
    for uploaded in files:
        photo_url = save_menu_photo(str(restaurant.id), uploaded)
        photo = MenuPhoto.objects.create(
            restaurant=restaurant,
            photo_url=photo_url,
            sort_order=next_order,
        )
        created.append(photo)
        next_order += 1

    payload = list_menu_photos(user, request=request)
    payload["created"] = [_serialize_photo(photo, request=request) for photo in created]
    return payload


@transaction.atomic
def delete_menu_photo(user: User, photo_id: str, request=None) -> dict:
    restaurant = get_restaurant_profile(user)
    try:
        photo = MenuPhoto.objects.get(id=photo_id, restaurant=restaurant)
    except MenuPhoto.DoesNotExist as exc:
        raise PeonyAPIException(
            code="MENU_PHOTO_NOT_FOUND",
            message="Menu photo not found.",
            http_status=404,
        ) from exc

    delete_stored_photo(photo.photo_url)
    photo.delete()
    _renumber_photos(restaurant)
    return list_menu_photos(user, request=request)


@transaction.atomic
def reorder_menu_photos(user: User, photo_ids: list[str], request=None) -> dict:
    restaurant = get_restaurant_profile(user)
    photos = list(_photos_queryset(restaurant))
    existing_ids = {str(photo.id) for photo in photos}

    if not photo_ids:
        raise PeonyAPIException(
            code="INVALID_REORDER",
            message="photo_ids is required.",
            http_status=400,
        )

    if len(photo_ids) != len(set(photo_ids)):
        raise PeonyAPIException(
            code="INVALID_REORDER",
            message="photo_ids must not contain duplicates.",
            http_status=400,
        )

    if set(photo_ids) != existing_ids:
        raise PeonyAPIException(
            code="INVALID_REORDER",
            message="photo_ids must include every current menu photo exactly once.",
            http_status=400,
        )

    photo_map = {str(photo.id): photo for photo in photos}
    for index, photo_id in enumerate(photo_ids, start=1):
        photo = photo_map[photo_id]
        if photo.sort_order != index:
            photo.sort_order = index
            photo.save(update_fields=["sort_order"])

    return list_menu_photos(user, request=request)


def list_public_menu_photos(restaurant, request=None) -> list[dict]:
    return [
        _serialize_photo(photo, request=request)
        for photo in _photos_queryset(restaurant)
    ]
