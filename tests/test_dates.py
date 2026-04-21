from datetime import UTC, datetime
from unittest.mock import patch

from utils.dates import in_last_days


@patch("utils.dates.utc_now")
def test_in_last_days_calendar_utc_not_time_of_day(mock_utc_now):
    mock_utc_now.return_value = datetime(2026, 4, 2, 15, 30, 0, tzinfo=UTC)
    # Window: Mar 26 .. Apr 2 inclusive (matches digest "today - 7 days" .. "today")
    assert in_last_days(datetime(2026, 3, 26, 0, 0, 0, tzinfo=UTC), 7) is True
    assert in_last_days(datetime(2026, 3, 26, 23, 59, 0, tzinfo=UTC), 7) is True
    assert in_last_days(datetime(2026, 3, 25, 23, 59, 0, tzinfo=UTC), 7) is False
    assert in_last_days(datetime(2026, 4, 2, 0, 0, 0, tzinfo=UTC), 7) is True
    assert in_last_days(datetime(2026, 4, 3, 0, 0, 0, tzinfo=UTC), 7) is False


def test_in_last_days_none():
    assert in_last_days(None, 7) is False
