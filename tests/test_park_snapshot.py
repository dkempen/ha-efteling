"""Tests for the derived park snapshot."""

from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from zoneinfo import ZoneInfo

import pytest

from custom_components.efteling.sensor import park_snapshot

if TYPE_CHECKING:
    from custom_components.efteling.data import EftelingData
    from custom_components.efteling.models import Event, Maintenance, OpeningHours


PARK_TZ = ZoneInfo("Europe/Amsterdam")


def test_calendar_date_accepts_iso_date_and_datetime() -> None:
    """Parse calendar dates regardless of a time suffix."""
    assert park_snapshot.calendar_date("2026-10-23") == date(2026, 10, 23)
    assert park_snapshot.calendar_date("2026-10-23T10:00:00") == date(2026, 10, 23)
    assert park_snapshot.calendar_date(None) is None
    assert park_snapshot.calendar_date("invalid") is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("DateFrom", "date_from"),
        ("OpeningHours", "opening_hours"),
        ("URLValue", "url_value"),
        ("lowerCase", "lower_case"),
        ("spaces-and punctuation", "spaces_and_punctuation"),
    ],
)
def test_normalize_key(value: str, expected: str) -> None:
    """Convert API field names to lowercase snake_case."""
    assert park_snapshot.normalize_key(value) == expected


def test_normalize_attribute_value_normalizes_nested_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Normalize nested keys and dates while preserving scalar values."""
    monkeypatch.setattr(
        park_snapshot.dt_util,
        "as_local",
        lambda value: value,
    )
    result = park_snapshot.normalize_attribute_value(
        {
            "DateFrom": "2026-10-23T00:00:00",
            "ShowDateTime": "2026-10-23T10:00:00+02:00",
            "NestedRecord": {"DateTo": "2026-10-25", "DisplayName": "Example"},
            "Values": [1, 2.5, True, None],
        }
    )
    assert result == {
        "date_from": "2026-10-23",
        "show_date_time": "2026-10-23T10:00:00+02:00",
        "nested_record": {"date_to": "2026-10-25", "display_name": "Example"},
        "values": [1, 2.5, True, None],
    }


def test_normalize_attribute_value_preserves_invalid_and_scalar_values() -> None:
    """Leave invalid date/time strings and non-container values unchanged."""
    assert (
        park_snapshot.normalize_attribute_value("invalid", key="DateFrom") == "invalid"
    )
    assert (
        park_snapshot.normalize_attribute_value("invalid", key="ShowDateTime")
        == "invalid"
    )
    assert park_snapshot.normalize_attribute_value(2.5) == 2.5
    assert park_snapshot.normalize_attribute_value(None) is None


def test_opening_hours_records_handles_invalid_dates_and_intervals() -> None:
    """Skip malformed days and preserve invalid interval values as nulls."""
    records = park_snapshot.opening_hours_records(
        [
            {"Date": "invalid", "OpeningHours": []},
            {"Date": "2026-10-23", "OpeningHours": []},
            {
                "Date": "2026-10-24",
                "OpeningHours": [{"Open": "invalid", "Close": None}],
            },
        ]
    )
    assert records == [
        {"date": "2026-10-23", "open": None, "close": None},
        {"date": "2026-10-24", "open": None, "close": None},
    ]


def test_opening_datetime_uses_park_timezone_and_rejects_invalid_input() -> None:
    """Combine local schedule dates and times while rejecting invalid values."""
    day = cast("OpeningHours", {"Date": "2026-10-23", "OpeningHours": []})
    result = park_snapshot.opening_datetime(day, "10:00")
    assert result == datetime(2026, 10, 23, 10, 0, tzinfo=PARK_TZ)
    assert park_snapshot.opening_datetime(day, None) is None
    assert park_snapshot.opening_datetime(day, "invalid") is None
    assert park_snapshot.opening_datetime({"Date": "bad"}, "10:00") is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [(1, "quiet"), (2, "normal"), (3, "busy"), (None, None), (99, None)],
)
def test_crowd_forecast_value(value: int | None, expected: str | None) -> None:
    """Convert supported crowd codes and reject unknown ones."""
    assert park_snapshot.crowd_forecast_value(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0, 0), (100, 100), (-1, None), (101, None), (None, None)],
)
def test_occupancy_forecast_value(value: int | None, expected: int | None) -> None:
    """Reject occupancy forecasts outside the percentage range."""
    assert park_snapshot.occupancy_forecast_value(value) == expected


def test_daily_forecasts_skip_invalid_dates() -> None:
    """Return normalized forecasts only for valid schedule dates."""
    days = cast(
        "list[OpeningHours]",
        [
            {"Date": "2026-10-23", "Crowded": 2, "Crowdedness": 100},
            {"Date": "invalid", "Crowded": 99, "Crowdedness": -1},
        ],
    )
    assert park_snapshot.daily_crowd_forecasts(days) == [
        {"date": "2026-10-23", "forecast": "normal"}
    ]
    assert park_snapshot.daily_occupancy_forecasts(days) == [
        {"date": "2026-10-23", "occupancy": 100}
    ]


def test_active_period_respects_inclusive_and_exclusive_end_dates() -> None:
    """Apply the caller's end-date inclusion policy and reject invalid ranges."""
    today = date(2026, 10, 23)
    active = cast(
        "Event",
        {"DateFrom": "2026-10-22", "DateTo": "2026-10-23", "Type": "winter"},
    )
    assert park_snapshot.active_period(active, today, inclusive_end=True)
    assert not park_snapshot.active_period(active, today, inclusive_end=False)
    assert not park_snapshot.active_period(
        {"DateFrom": "invalid", "DateTo": "2026-10-24"}, today, inclusive_end=True
    )
    assert not park_snapshot.active_period(
        {"DateFrom": "2026-10-24", "DateTo": "2026-10-23"}, today, inclusive_end=True
    )


@pytest.mark.parametrize("value", [0, 10])
def test_valid_wait_preserves_nonnegative_values(value: int) -> None:
    """Preserve zero-minute waits and positive wait times."""
    assert park_snapshot.valid_wait(value) == value


def test_valid_wait_rejects_negative_and_missing_values() -> None:
    """Ignore negative and missing wait times."""
    assert park_snapshot.valid_wait(-1) is None
    assert park_snapshot.valid_wait(None) is None


def _snapshot_data(
    *,
    opening_hours: list[dict[str, object]],
    maintenance: list[dict[str, object]] | None = None,
    events: list[dict[str, object]] | None = None,
    pois: dict[str, dict[str, str]] | None = None,
    wait_times: dict[str, dict[str, object]] | None = None,
) -> EftelingData:
    """Build coordinator-shaped test data for snapshot calculations."""
    return cast(
        "EftelingData",
        SimpleNamespace(
            park_info_coordinator=SimpleNamespace(
                data={
                    "OpeningHours": opening_hours,
                    "Maintenance": maintenance or [],
                    "Events": events or [],
                }
            ),
            poi_coordinator=SimpleNamespace(data=pois or {}),
            wait_times_coordinator=SimpleNamespace(data=wait_times or {}),
        ),
    )


def test_build_snapshot_uses_only_qualifying_open_attractions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Calculate today's schedule and average from qualifying live records."""
    now = datetime(2026, 10, 23, 12, 0, tzinfo=PARK_TZ)
    monkeypatch.setattr(park_snapshot.dt_util, "now", lambda _tz=None: now)
    response = {
        "Date": "2026-10-23",
        "OpeningHours": [
            {"Open": "10:00", "Close": "20:00"},
            {"Open": "08:00", "Close": "09:00"},
        ],
        "Crowded": 2,
        "Crowdedness": 60,
    }
    data = _snapshot_data(
        opening_hours=[response],
        maintenance=[
            {"DateFrom": "2026-10-22", "DateTo": "2026-10-24", "Name": "Python"}
        ],
        events=[
            {
                "DateFrom": "2026-10-23",
                "DateTo": "2026-10-23",
                "Type": "winter",
            }
        ],
        pois={
            "1": {"id": "1", "name": "Python", "category": "attraction"},
            "2": {"id": "2", "name": "Aquanura", "category": "show"},
            "4": {"id": "4", "name": "Unnamed", "category": "attraction"},
        },
        wait_times={
            "1": {"Id": "1", "Name": "Python", "State": "open", "WaitingTime": 20},
            "2": {"Id": "2", "Name": "Aquanura", "State": "open", "WaitingTime": 50},
            "3": {"Id": "3", "Name": "Unknown", "State": "open", "WaitingTime": 100},
            "4": {"Id": "4", "Name": "Fallback", "State": "open", "WaitingTime": 1},
            "5": {"Id": "5", "Name": "Closed", "State": "closed", "WaitingTime": 2},
            "6": {"Id": "6", "Name": "Negative", "State": "open", "WaitingTime": -1},
        },
    )

    result = park_snapshot.build_snapshot(data)
    assert result["today"] == response
    assert len(result["maintenance_today"]) == 1
    assert len(result["events_today"]) == 1
    assert result["opening_time"] == datetime(2026, 10, 23, 8, 0, tzinfo=PARK_TZ)
    assert result["closing_time"] == datetime(2026, 10, 23, 20, 0, tzinfo=PARK_TZ)
    assert result["average_wait_time"] == 10
    assert result["samples"] == [
        {"id": "1", "name": "Python", "minutes": 20},
        {"id": "4", "name": "Unnamed", "minutes": 1},
    ]


def test_build_snapshot_handles_missing_day_and_invalid_intervals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return empty schedule values when no valid local-day interval exists."""
    monkeypatch.setattr(
        park_snapshot.dt_util,
        "now",
        lambda _tz=None: datetime(2026, 10, 23, 12, 0, tzinfo=PARK_TZ),
    )
    data = _snapshot_data(
        opening_hours=[
            {
                "Date": "2026-10-23",
                "OpeningHours": [{"Open": "20:00", "Close": "10:00"}],
            },
            {"Date": "invalid", "OpeningHours": []},
        ],
    )
    result = park_snapshot.build_snapshot(data)
    assert result["today"] is not None
    assert result["opening_time"] is None
    assert result["closing_time"] is None
    assert result["average_wait_time"] is None


def test_as_records_normalizes_fields_and_excludes_requested_keys() -> None:
    """Convert records to normalized state attributes and omit selected fields."""
    result = park_snapshot.as_records(
        cast(
            "list[Maintenance]",
            [
                {
                    "DateFrom": "2026-10-23T00:00:00",
                    "Name": "Python",
                    "DateTo": "2026-10-24",
                },
            ],
        ),
        exclude_keys={"Name"},
    )
    assert result == [{"date_from": "2026-10-23", "date_to": "2026-10-24"}]
