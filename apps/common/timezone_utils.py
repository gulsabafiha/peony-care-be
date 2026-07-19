import math
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

SGT = ZoneInfo("Asia/Singapore")
WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def now_sgt() -> datetime:
    return datetime.now(SGT)


def today_sgt() -> date:
    return now_sgt().date()


def next_midnight_sgt() -> datetime:
    today = now_sgt().date()
    midnight = datetime.combine(today + timedelta(days=1), time.min, tzinfo=SGT)
    return midnight


def start_of_week_sgt(day: date | None = None) -> date:
    """Monday of the SGT week containing ``day`` (defaults to today)."""
    day = day or today_sgt()
    return day - timedelta(days=day.weekday())


def week_bounds_sgt(day: date | None = None) -> tuple[date, date]:
    """Inclusive start (Mon) and exclusive end (next Mon) for the SGT week."""
    start = start_of_week_sgt(day)
    return start, start + timedelta(days=7)


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


def format_relative_ago(dt: datetime, *, now: datetime | None = None) -> str:
    """Human-friendly relative time, e.g. ``2h ago``, ``yesterday``, ``Jun 4``."""
    now = now or now_sgt()
    moment = dt.astimezone(SGT)
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
    if moment.date() == today_sgt() - timedelta(days=1):
        return "yesterday"
    return f"{moment.strftime('%b')} {moment.day}"


def format_day_label(day: date, *, today: date | None = None) -> str:
    today = today or today_sgt()
    if day == today:
        return "Today"
    if day == today - timedelta(days=1):
        return "Yesterday"
    return f"{day.strftime('%b')} {day.day}"


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
