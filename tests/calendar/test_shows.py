"""Tests for show calendar event generation."""

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from custom_components.efteling_park.calendar.shows import build_show_calendar_events

if TYPE_CHECKING:
    from custom_components.efteling_park.models import AttractionInfo, Poi


def test_show_calendar_parses_naive_times_and_duration_fallback() -> None:
    """Parse naive local showtimes and derive an end from their duration."""
    wait_times: dict[str, AttractionInfo] = {
        "aquanura": {
            "Id": "aquanura",
            "Name": "Aquanura",
            "State": "open",
            "ShowTimes": [
                {
                    "StartDateTime": "2026-11-20T14:00:00",
                    "Duration": 20,
                    "Edition": "Efteling Symphonica",
                },
                {"StartDateTime": "not-a-date", "Duration": 20},
            ],
        },
        "python": {
            "Id": "python",
            "Name": "Python",
            "State": "open",
            "ShowTimes": [
                {
                    "StartDateTime": "2026-11-20T14:00:00+01:00",
                    "Duration": 10,
                }
            ],
        },
    }
    pois: dict[str, Poi] = {
        "aquanura": {
            "id": "aquanura",
            "name": "Aquanura",
            "category": "show",
        },
        "python": {
            "id": "python",
            "name": "Python",
            "category": "attraction",
        },
    }
    events = build_show_calendar_events(wait_times, pois)

    assert len(events) == 1
    assert events[0].summary == "Aquanura"
    assert events[0].description == "Efteling Symphonica"
    assert events[0].start == datetime(2026, 11, 20, 13, 0, tzinfo=UTC)
    start = events[0].start
    assert isinstance(start, datetime)
    assert events[0].end == start + timedelta(minutes=20)
