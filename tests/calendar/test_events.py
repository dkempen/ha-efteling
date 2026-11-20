"""Tests for park event calendar event generation."""

from datetime import date
from typing import TYPE_CHECKING

from custom_components.efteling_park.calendar.events import build_events_calendar_events

if TYPE_CHECKING:
    from custom_components.efteling_park.models import Event


def test_events_calendar_combines_winter_and_business_events() -> None:
    """Include both event types with their inclusive end dates."""
    source_events: list[Event] = [
        {
            "Type": "winter",
            "Name": "Winter Efteling",
            "DateFrom": "2026-11-16 01:00",
            "DateTo": "2027-02-01 01:00",
        },
        {
            "Type": "business",
            "Name": "Business event",
            "DateFrom": "2026-11-22 01:00",
            "DateTo": "2026-11-22 01:00",
            "Description": "<p>Grote drukte verwacht.</p>",
        },
        {
            "Type": "other",
            "DateFrom": "2026-11-23 01:00",
            "DateTo": "2026-11-23 01:00",
        },
    ]

    events = build_events_calendar_events(source_events, language="nl")

    assert len(events) == 2
    assert events[0].start == date(2026, 11, 16)
    assert events[0].end == date(2027, 2, 2)
    assert events[0].description is None
    assert events[1].start == date(2026, 11, 22)
    assert events[1].end == date(2026, 11, 23)
    assert events[1].description == "Grote drukte verwacht."
