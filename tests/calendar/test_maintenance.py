"""Tests for maintenance calendar event generation."""

from datetime import date
from typing import TYPE_CHECKING

from custom_components.efteling_park.calendar.maintenance import (
    build_maintenance_calendar_events,
)

if TYPE_CHECKING:
    from custom_components.efteling_park.models import Maintenance


def test_maintenance_calendar_uses_exclusive_end_date() -> None:
    """Keep the maintenance end date exclusive, matching the sensor logic."""
    maintenance_items: list[Maintenance] = [
        {
            "Name": "Danse Macabre",
            "DateFrom": "2026-10-26T00:00:00",
            "DateTo": "2026-11-06T00:00:00",
        }
    ]

    events = build_maintenance_calendar_events(
        maintenance_items,
    )

    assert len(events) == 1
    assert events[0].summary == "Danse Macabre"
    assert events[0].start == date(2026, 10, 26)
    assert events[0].end == date(2026, 11, 6)
    assert events[0].description is None


def test_maintenance_calendar_ignores_records_without_names() -> None:
    """Skip malformed records instead of creating events without a summary."""
    maintenance_items: list[Maintenance] = [
        {
            "DateFrom": "2026-10-26T00:00:00",
            "DateTo": "2026-11-06T00:00:00",
        },
        {
            "Name": None,
            "DateFrom": "2026-10-26T00:00:00",
            "DateTo": "2026-11-06T00:00:00",
        },
    ]

    assert build_maintenance_calendar_events(maintenance_items) == []
