"""Shared helpers for parsing show data."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.util import dt as dt_util

from custom_components.efteling_park.const import PARK_TIME_ZONE

if TYPE_CHECKING:
    from datetime import datetime


def parse_show_datetime(value: str | None) -> datetime | None:
    """Parse a show timestamp, assuming Efteling local time if no zone exists."""
    if value is None:
        return None

    parsed = dt_util.parse_datetime(value)
    if parsed is None:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=PARK_TIME_ZONE)

    return dt_util.as_utc(parsed)


def parse_show_duration(value: int | str | None) -> int | None:
    """Return a positive integer duration when the API value is valid."""
    if value is None:
        return None

    try:
        duration = int(value)
    except ValueError:
        return None

    return duration if duration > 0 else None
