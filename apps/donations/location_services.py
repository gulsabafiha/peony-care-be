from __future__ import annotations

from apps.accounts.models import User
from apps.common.geocoding import (
    extract_postal_code,
    reverse_geocode,
    search_locations,
)
from apps.donations.restaurant_services import (
    get_restaurant_profile,
    update_restaurant_profile_data,
)


def search_restaurant_locations(query: str) -> dict:
    results = search_locations(query)
    return {
        "query": query,
        "count": len(results),
        "results": results,
    }


def reverse_restaurant_location(latitude: float, longitude: float) -> dict:
    return reverse_geocode(latitude, longitude)


def confirm_restaurant_location(user: User, data: dict, request=None) -> dict:
    """Persist the selected map pin onto the restaurant profile."""
    address = data["address"]
    latitude = data["latitude"]
    longitude = data["longitude"]
    postal_code = data.get("postal_code") or extract_postal_code(address)

    profile_data = {
        "address": address,
        "latitude": latitude,
        "longitude": longitude,
    }
    restaurant = update_restaurant_profile_data(user, profile_data, request=request)

    # Ensure postal is set even if address parsing missed it.
    if postal_code and restaurant.get("postal_code") != postal_code:
        profile = get_restaurant_profile(user)
        profile.postal_code = postal_code
        profile.save(update_fields=["postal_code"])
        restaurant["postal_code"] = postal_code

    return {
        "message": "Location confirmed.",
        "selected_location": {
            "address_line": data.get("address_line") or address.split(",")[0].strip(),
            "address": address,
            "postal_code": restaurant.get("postal_code") or postal_code,
            "latitude": float(restaurant["latitude"]),
            "longitude": float(restaurant["longitude"]),
            "subtitle": (
                f"Singapore {restaurant.get('postal_code') or postal_code} · "
                f"{float(restaurant['latitude']):.5f}, {float(restaurant['longitude']):.5f}"
            ),
        },
        "restaurant": restaurant,
    }
