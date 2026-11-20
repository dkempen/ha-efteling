"""Tests for opening-hours calendar event generation."""

from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from custom_components.efteling_park.calendar.opening_hours import (
    build_opening_hours_events,
)

if TYPE_CHECKING:
    from custom_components.efteling_park.models import OpeningHours


def test_opening_hours_calendar_creates_timed_events() -> None:
    """Create a separate timed event for every opening interval."""
    opening_hours: list[OpeningHours] = [
        {
            "Date": "2026-11-20",
            "Crowded": 3,
            "Crowdedness": 83,
            "OpeningHours": [
                {"Open": "10:00", "Close": "18:00"},
                {"Open": "19:00", "Close": "22:00"},
            ],
        },
        {"Date": "2026-11-21", "OpeningHours": []},
        {
            "Date": "invalid",
            "OpeningHours": [{"Open": "10:00", "Close": "18:00"}],
        },
        {
            "Date": "2026-11-22",
            "OpeningHours": [{"Open": "18:00", "Close": "17:00"}],
        },
    ]

    events = build_opening_hours_events(opening_hours, language="en")

    assert len(events) == 2
    assert events[0].summary == "Efteling open"
    assert events[0].description == "Crowd level: Busy\nOccupancy: 83%"
    assert events[0].start == datetime(
        2026,
        11,
        20,
        10,
        0,
        tzinfo=ZoneInfo("Europe/Amsterdam"),
    )
    assert events[0].end == datetime(
        2026,
        11,
        20,
        18,
        0,
        tzinfo=ZoneInfo("Europe/Amsterdam"),
    )
    assert isinstance(events[1].start, datetime)
    assert isinstance(events[1].end, datetime)
    assert events[1].start.hour == 19
    assert events[1].end.hour == 22
