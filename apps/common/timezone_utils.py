import math
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

SGT = ZoneInfo("Asia/Singapore")


def now_sgt() -> datetime:
    return datetime.now(SGT)


def today_sgt() -> date:
    return now_sgt().date()


def next_midnight_sgt() -> datetime:
    today = now_sgt().date()
    midnight = datetime.combine(today + timedelta(days=1), time.min, tzinfo=SGT)
    return midnight


def _format_time(dt: datetime) -> str:
    return dt.strftime("%I:%M %p").lstrip("0")


def format_pickup_window(pickup_start: datetime, pickup_end: datetime) -> str:
    start = pickup_start.astimezone(SGT)
    end = pickup_end.astimezone(SGT)
    today = now_sgt().date()
    day_label = "Today" if start.date() == today else start.strftime("%a, %d %b")
    if start.date() == end.date():
        return f"{day_label}, {_format_time(start)} — {_format_time(end)}"
    return f"{_format_time(start)} — {_format_time(end)}"


def bounding_box(lat: float, lng: float, radius_km: float) -> tuple[float, float, float, float]:
    """Return min_lat, max_lat, min_lng, max_lng for a rough pre-filter."""
    lat_delta = radius_km / 111.0
    lng_delta = radius_km / (111.0 * max(math.cos(math.radians(lat)), 0.01))
    return (
        lat - lat_delta,
        lat + lat_delta,
        lng - lng_delta,
        lng + lng_delta,
    )
