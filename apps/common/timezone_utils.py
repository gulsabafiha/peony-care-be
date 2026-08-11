import math
import re
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

# App supports Singapore and Bangladesh; default remains Singapore for legacy call sites.
SGT = ZoneInfo("Asia/Singapore")
BDT = ZoneInfo("Asia/Dhaka")
DEFAULT_TZ = SGT

WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

_COUNTRY_TZ = {
    "singapore": SGT,
    "bangladesh": BDT,
    "sg": SGT,
    "bd": BDT,
}


def timezone_for_postal_code(postal_code: str | None) -> ZoneInfo:
    """Map restaurant postal code to local TZ (SG=6 digits, BD=4 digits)."""
    code = (postal_code or "").strip()
    if len(code) == 4 and code.isdigit():
        return BDT
    return SGT


def timezone_for_country(country: str | None) -> ZoneInfo:
    if not country:
        return DEFAULT_TZ
    return _COUNTRY_TZ.get(country.strip().lower(), DEFAULT_TZ)


def timezone_for_phone(phone_e164: str | None) -> ZoneInfo:
    phone = phone_e164 or ""
    if phone.startswith("+880"):
        return BDT
    if phone.startswith("+65"):
        return SGT
    return DEFAULT_TZ


def timezone_for_restaurant(restaurant) -> ZoneInfo:
    """Resolve a restaurant's local timezone from postal code (preferred) or address."""
    postal = getattr(restaurant, "postal_code", None) or ""
    if postal:
        return timezone_for_postal_code(postal)
    address = getattr(restaurant, "address", "") or ""
    lowered = address.lower()
    if "bangladesh" in lowered or "dhaka" in lowered:
        return BDT
    if "singapore" in lowered:
        return SGT
    if re.search(r"\b\d{6}\b", address):
        return SGT
    if re.search(r"\b\d{4}\b", address):
        return BDT
    return DEFAULT_TZ


def now_in(tz: ZoneInfo | None = None) -> datetime:
    return datetime.now(tz or DEFAULT_TZ)


def today_in(tz: ZoneInfo | None = None) -> date:
    return now_in(tz).date()


def now_sgt() -> datetime:
    """Backward-compatible alias; prefer ``now_in(timezone_for_…)`` for country-aware code."""
    return now_in(SGT)


def today_sgt() -> date:
    return today_in(SGT)


def next_midnight_in(tz: ZoneInfo | None = None) -> datetime:
    zone = tz or DEFAULT_TZ
    today = today_in(zone)
    return datetime.combine(today + timedelta(days=1), time.min, tzinfo=zone)


def next_midnight_sgt() -> datetime:
    return next_midnight_in(SGT)


def start_of_week_in(day: date | None = None, *, tz: ZoneInfo | None = None) -> date:
    """Monday of the local week containing ``day`` (defaults to today in ``tz``)."""
    day = day or today_in(tz)
    return day - timedelta(days=day.weekday())


def start_of_week_sgt(day: date | None = None) -> date:
    return start_of_week_in(day, tz=SGT)


def week_bounds_in(day: date | None = None, *, tz: ZoneInfo | None = None) -> tuple[date, date]:
    """Inclusive start (Mon) and exclusive end (next Mon) for the local week."""
    start = start_of_week_in(day, tz=tz)
    return start, start + timedelta(days=7)


def week_bounds_sgt(day: date | None = None) -> tuple[date, date]:
    return week_bounds_in(day, tz=SGT)


def to_local(dt: datetime, tz: ZoneInfo | None = None) -> datetime:
    zone = tz or DEFAULT_TZ
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(zone)


def to_local_iso(dt: datetime, tz: ZoneInfo | None = None) -> str:
    """Serialize an instant in the given local timezone (country-aware)."""
    return to_local(dt, tz).isoformat()


def _format_time(dt: datetime) -> str:
    return dt.strftime("%I:%M %p").lstrip("0")


def format_pickup_window(
    pickup_start: datetime,
    pickup_end: datetime,
    *,
    tz: ZoneInfo | None = None,
) -> str:
    zone = tz or DEFAULT_TZ
    start = to_local(pickup_start, zone)
    end = to_local(pickup_end, zone)
    today = today_in(zone)
    day_label = "Today" if start.date() == today else start.strftime("%a, %d %b")
    if start.date() == end.date():
        return f"{day_label}, {_format_time(start)} — {_format_time(end)}"
    return f"{day_label}, {_format_time(start)} — {end.strftime('%a, %d %b')}, {_format_time(end)}"


def format_pickup_window_short(
    pickup_start: datetime,
    pickup_end: datetime,
    *,
    tz: ZoneInfo | None = None,
) -> str:
    zone = tz or DEFAULT_TZ
    start = to_local(pickup_start, zone)
    end = to_local(pickup_end, zone)
    return f"{_format_time(start)} – {_format_time(end)}"


def format_relative_ago(
    dt: datetime,
    *,
    now: datetime | None = None,
    tz: ZoneInfo | None = None,
) -> str:
    """Human-friendly relative time, e.g. ``2h ago``, ``yesterday``, ``Jun 4``."""
    zone = tz or DEFAULT_TZ
    now = now or now_in(zone)
    moment = to_local(dt, zone)
    delta = now - moment
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        minutes = max(seconds // 60, 1)
        return f"{minutes}m ago"
    if seconds < 86400:
        hours = max(seconds // 3600, 1)
        return f"{hours}h ago"
    if moment.date() == today_in(zone) - timedelta(days=1):
        return "yesterday"
    return f"{moment.strftime('%b')} {moment.day}"


def format_day_label(day: date, *, today: date | None = None, tz: ZoneInfo | None = None) -> str:
    today = today or today_in(tz)
    if day == today:
        return "Today"
    if day == today - timedelta(days=1):
        return "Yesterday"
    return f"{day.strftime('%b')} {day.day}"


def format_clock_time(dt: datetime, *, tz: ZoneInfo | None = None) -> str:
    return to_local(dt, tz).strftime("%I:%M %p").lstrip("0")


def format_countdown_until(
    end: datetime,
    *,
    now: datetime | None = None,
    tz: ZoneInfo | None = None,
) -> str | None:
    zone = tz or DEFAULT_TZ
    now = now or now_in(zone)
    end = to_local(end, zone)
    seconds = int((end - now).total_seconds())
    if seconds <= 0:
        return "Window closed"
    hours, rem = divmod(seconds, 3600)
    minutes = rem // 60
    if hours:
        return f"{hours}h {minutes}m until window closes"
    return f"{minutes}m until window closes"


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
