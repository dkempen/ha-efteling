"""Derive the current Park snapshot from coordinator data."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import date, datetime, time
from math import isfinite
from typing import TYPE_CHECKING, TypedDict

from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from custom_components.efteling.data import EftelingData
    from custom_components.efteling.models import (
        Event,
        Maintenance,
        OpeningHours,
        ParkInfoResponse,
    )


class WaitSample(TypedDict):
    """Qualifying live attraction wait time."""

    id: str
    name: str
    minutes: int | float


class ParkSnapshot(TypedDict):
    """Derived current-day view of all source coordinator data."""

    today: OpeningHours | None
    maintenance_today: list[Maintenance]
    events_today: list[Event]
    opening_time: datetime | None
    closing_time: datetime | None
    samples: list[WaitSample]
    average_wait_time: int | None


def calendar_date(value: object) -> date | None:
    """Parse an ISO calendar date, ignoring a time suffix if present."""
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


_DATE_ONLY_KEYS = frozenset({"date", "date_from", "date_to"})
MAX_OCCUPANCY = 100


def normalize_key(value: str) -> str:
    """Convert API field names to lowercase snake_case."""
    value = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", value)
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    return re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()


def normalize_attribute_value(value: object, *, key: str | None = None) -> object:
    """Normalize API record keys and date-only values recursively."""
    normalized_key = normalize_key(key) if key is not None else None
    if isinstance(value, Mapping):
        return {
            normalize_key(str(item_key)): normalize_attribute_value(
                item_value, key=str(item_key)
            )
            for item_key, item_value in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [normalize_attribute_value(item, key=normalized_key) for item in value]
    if normalized_key in _DATE_ONLY_KEYS and isinstance(value, str):
        parsed_date = calendar_date(value)
        return parsed_date.isoformat() if parsed_date is not None else value
    if (
        normalized_key is not None
        and normalized_key.endswith("_date_time")
        and isinstance(value, str)
    ):
        parsed_datetime = dt_util.parse_datetime(value)
        if parsed_datetime is not None:
            return dt_util.as_local(parsed_datetime).isoformat()
    return value


def opening_hours_records(
    days: Sequence[Mapping[str, object]],
) -> list[dict[str, str | None]]:
    """Return flat opening-interval records using ISO dates and datetimes."""
    records: list[dict[str, str | None]] = []
    for day in days:
        parsed_date = calendar_date(day.get("Date"))
        if parsed_date is None:
            continue
        raw_intervals = day.get("OpeningHours") or []
        intervals = (
            [interval for interval in raw_intervals if isinstance(interval, Mapping)]
            if isinstance(raw_intervals, Sequence)
            else []
        )
        if not intervals:
            records.append(
                {"date": parsed_date.isoformat(), "open": None, "close": None}
            )
            continue
        for interval in intervals:
            opened = opening_datetime(day, interval.get("Open"))
            closed = opening_datetime(day, interval.get("Close"))
            records.append(
                {
                    "date": parsed_date.isoformat(),
                    "open": opened.isoformat() if opened is not None else None,
                    "close": closed.isoformat() if closed is not None else None,
                }
            )
    return records


def crowd_forecast_value(value: object) -> str | None:
    """Convert the Efteling crowd forecast code to its stable enum value."""
    return {"1": "quiet", "2": "normal", "3": "busy"}.get(str(value))


def occupancy_forecast_value(value: object) -> int | None:
    """Return a valid occupancy percentage from the API value."""
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    try:
        number = int(value)
    except TypeError, ValueError:
        return None
    return number if 0 <= number <= MAX_OCCUPANCY else None


def daily_crowd_forecasts(
    days: Sequence[Mapping[str, object]],
) -> list[dict[str, str | None]]:
    """Return normalized crowd forecast rows with valid dates."""
    return [
        {
            "date": parsed_date.isoformat(),
            "forecast": crowd_forecast_value(item.get("Crowded")),
        }
        for item in days
        if (parsed_date := calendar_date(item.get("Date"))) is not None
    ]


def daily_occupancy_forecasts(
    days: Sequence[Mapping[str, object]],
) -> list[dict[str, str | int | None]]:
    """Return normalized occupancy forecast rows with valid dates."""
    return [
        {
            "date": parsed_date.isoformat(),
            "occupancy": occupancy_forecast_value(item.get("Crowdedness")),
        }
        for item in days
        if (parsed_date := calendar_date(item.get("Date"))) is not None
    ]


def active_period(
    item: Mapping[str, object], today: date, *, inclusive_end: bool
) -> bool:
    """Return whether today falls within the item's date range."""
    start = calendar_date(item.get("DateFrom"))
    end = calendar_date(item.get("DateTo"))
    return (
        start is not None
        and end is not None
        and start <= today
        and (today <= end if inclusive_end else today < end)
    )


def opening_datetime(day: Mapping[str, object], value: object) -> datetime | None:
    """Combine an opening-hours date and time in the local timezone."""
    date_value = day.get("Date")
    if not isinstance(value, str) or not isinstance(date_value, str):
        return None
    try:
        parsed_date = date.fromisoformat(date_value[:10])
        parsed_time = time.fromisoformat(value)
    except ValueError:
        return None
    return datetime.combine(parsed_date, parsed_time, tzinfo=dt_util.now().tzinfo)


def valid_wait(value: object) -> int | float | None:
    """Return a valid nonnegative wait-time value."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if value >= 0 and isfinite(value) else None


def build_snapshot(data: EftelingData) -> ParkSnapshot:
    """Derive today's Park state and qualifying live attraction samples."""
    response: ParkInfoResponse = data.park_info_coordinator.data
    today = dt_util.now().date()
    today_record = next(
        (
            item
            for item in response["OpeningHours"]
            if calendar_date(item.get("Date")) == today
        ),
        None,
    )

    intervals: list[tuple[datetime, datetime]] = []
    if today_record is not None:
        for interval in today_record.get("OpeningHours") or []:
            opened = opening_datetime(today_record, interval.get("Open"))
            closed = opening_datetime(today_record, interval.get("Close"))
            if opened is not None and closed is not None and closed > opened:
                intervals.append((opened, closed))
    intervals.sort(key=lambda interval: interval[0])

    maintenance_today = [
        item
        for item in response["Maintenance"]
        if active_period(item, today, inclusive_end=False)
    ]
    events_today = [
        item
        for item in response["Events"]
        if active_period(item, today, inclusive_end=True)
    ]

    samples: list[WaitSample] = []
    for attraction_id, attraction in data.wait_times_coordinator.data.items():
        poi = data.poi_coordinator.data.get(attraction_id)
        minutes = valid_wait(attraction.get("WaitingTime"))
        if (
            poi is None
            or poi.get("category") != "attraction"
            or attraction.get("State") != "open"
            or minutes is None
        ):
            continue
        samples.append(
            {
                "id": attraction_id,
                "name": str(poi.get("name") or attraction.get("Name") or attraction_id),
                "minutes": minutes,
            }
        )

    average = (
        round(sum(sample["minutes"] for sample in samples) / len(samples))
        if samples
        else None
    )
    return {
        "today": today_record,
        "maintenance_today": maintenance_today,
        "events_today": events_today,
        "opening_time": intervals[0][0] if intervals else None,
        "closing_time": intervals[-1][1] if intervals else None,
        "samples": samples,
        "average_wait_time": average,
    }


def as_records(
    items: Sequence[Mapping[str, object]],
    *,
    exclude_keys: frozenset[str] | set[str] = frozenset(),
) -> list[dict[str, object]]:
    """Return API records with recursively normalized keys and date values."""
    return [
        {
            normalize_key(str(key)): normalize_attribute_value(value, key=str(key))
            for key, value in item.items()
            if str(key) not in exclude_keys
        }
        for item in items
    ]
