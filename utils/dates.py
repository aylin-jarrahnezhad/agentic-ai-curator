from datetime import UTC, date, datetime, timedelta

from dateutil import parser


def utc_now() -> datetime:
    return datetime.now(UTC)


def parse_date(date_text: str | None) -> datetime | None:
    if not date_text:
        return None
    try:
        dt = parser.parse(date_text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except Exception:
        return None


def to_iso_datetime_utc(dt: datetime | None) -> str | None:
    """UTC instant as ``YYYY-MM-DDTHH:MM:SSZ`` for JSON filtering and sorting."""
    if dt is None:
        return None
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_iso_date_utc(dt: datetime | None) -> str | None:
    """Calendar day in UTC as ``YYYY-MM-DD``."""
    if dt is None:
        return None
    return dt.astimezone(UTC).date().isoformat()


def in_last_days(dt: datetime | None, days: int) -> bool:
    """True if ``dt``'s calendar day (UTC) falls in the inclusive range matching the digest window:
    from ``today - days`` through ``today`` (UTC dates only; hour/minute ignored).
    """
    if dt is None:
        return False
    item_day: date = dt.astimezone(UTC).date()
    today: date = utc_now().date()
    start: date = today - timedelta(days=days)
    return start <= item_day <= today
