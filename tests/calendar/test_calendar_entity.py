"""Tests for shared calendar entity helpers."""

from datetime import date

import pytest

from custom_components.efteling_park.calendar.calendar_entity import (
    EftelingCalendarEntity,
    create_date_range_event,
    parse_calendar_date,
)


def test_parse_calendar_date_rejects_missing_and_invalid_values() -> None:
    """Return no date when the source value is missing or malformed."""
    assert parse_calendar_date(None) is None
    assert parse_calendar_date("not-a-date") is None


@pytest.mark.parametrize(
    "date_range",
    [
        ("not-a-date", "2026-11-21"),
        ("2026-11-20", "not-a-date"),
        ("2026-11-21", "2026-11-20"),
    ],
)
def test_create_date_range_event_rejects_invalid_ranges(
    date_range: tuple[str, str],
) -> None:
    """Reject malformed dates and ranges without a positive duration."""
    assert (
        create_date_range_event(
            date_range,
            summary="Event",
            description=None,
            uid="event",
            end_inclusive=False,
        )
        is None
    )


def test_calendar_entity_requires_event_implementation() -> None:
    """Require concrete calendar entities to implement event generation."""
    entity = object.__new__(EftelingCalendarEntity)

    with pytest.raises(NotImplementedError):
        entity._get_events()


def test_create_date_range_event_returns_all_day_event() -> None:
    """Create an all-day event from valid dates."""
    event = create_date_range_event(
        ("2026-11-20", "2026-11-21"),
        summary="Event",
        description=None,
        uid="event",
        end_inclusive=False,
    )

    assert event is not None
    assert event.start == date(2026, 11, 20)
    assert event.end == date(2026, 11, 21)
