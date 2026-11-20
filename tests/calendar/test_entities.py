"""Tests for Efteling calendar entities through Home Assistant."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from homeassistant.components.calendar import CalendarEntity
from homeassistant.components.calendar.const import DATA_COMPONENT

from custom_components.efteling_park.const import PARK_TIME_ZONE

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_registry import RegistryEntry
    from pytest_homeassistant.common import MockConfigEntry


def _get_calendar(
    hass: HomeAssistant,
    entity_id: str,
) -> CalendarEntity:
    """Return a registered Efteling calendar entity."""
    entity = hass.data[DATA_COMPONENT].get_entity(entity_id)
    assert isinstance(entity, CalendarEntity)
    return entity


async def test_opening_hours_calendar(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    entity_registry_entry: Callable[[MockConfigEntry, str], RegistryEntry],
) -> None:
    """Create timed opening events and include the daily forecasts."""
    loaded_entry.runtime_data.park_info_coordinator.async_set_updated_data(
        {
            "OpeningHours": [
                {
                    "Date": "2026-11-20",
                    "OpeningHours": [
                        {"Open": "10:00", "Close": "18:00"},
                        {"Open": "19:00", "Close": "22:00"},
                    ],
                    "Crowded": 3,
                    "Crowdedness": 83,
                }
            ],
            "Maintenance": [],
            "Events": [],
        }
    )
    await hass.async_block_till_done()

    registry_entry = entity_registry_entry(
        loaded_entry,
        "opening_hours",
    )
    calendar = _get_calendar(hass, registry_entry.entity_id)

    tz = PARK_TIME_ZONE
    events = await calendar.async_get_events(
        hass,
        datetime(2026, 11, 20, 0, 0, tzinfo=tz),
        datetime(2026, 11, 21, 0, 0, tzinfo=tz),
    )

    assert len(events) == 2
    assert events[0].start == datetime(2026, 11, 20, 10, 0, tzinfo=tz)
    assert events[0].end == datetime(2026, 11, 20, 18, 0, tzinfo=tz)
    assert events[1].start == datetime(2026, 11, 20, 19, 0, tzinfo=tz)
    assert events[1].end == datetime(2026, 11, 20, 22, 0, tzinfo=tz)
    assert events[0].description is not None
    assert "83%" in events[0].description


async def test_park_events_calendar_uses_inclusive_end_dates(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    entity_registry_entry: Callable[[MockConfigEntry, str], RegistryEntry],
) -> None:
    """Represent Park event end dates as inclusive all-day events."""
    loaded_entry.runtime_data.park_info_coordinator.async_set_updated_data(
        {
            "OpeningHours": [],
            "Maintenance": [],
            "Events": [
                {
                    "DateFrom": "2026-11-20T01:00:00",
                    "DateTo": "2026-11-22T01:00:00",
                    "Type": "winter",
                    "Name": "Winter Efteling",
                },
                {
                    "DateFrom": "2026-11-21T01:00:00",
                    "DateTo": "2026-11-21T01:00:00",
                    "Type": "business",
                    "Name": "Business event",
                },
            ],
        }
    )
    await hass.async_block_till_done()

    registry_entry = entity_registry_entry(loaded_entry, "events")
    calendar = _get_calendar(hass, registry_entry.entity_id)

    events = await calendar.async_get_events(
        hass,
        datetime(2026, 11, 20, 0, 0, tzinfo=PARK_TIME_ZONE),
        datetime(2026, 11, 24, 0, 0, tzinfo=PARK_TIME_ZONE),
    )

    assert len(events) == 2
    winter = next(event for event in events if event.summary == "Winter Efteling")
    business = next(event for event in events if event.summary == "Business event")
    assert winter.start == date(2026, 11, 20)
    assert winter.end == date(2026, 11, 23)
    assert business.start == date(2026, 11, 21)
    assert business.end == date(2026, 11, 22)


async def test_maintenance_calendar_uses_exclusive_end_dates(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    entity_registry_entry: Callable[[MockConfigEntry, str], RegistryEntry],
) -> None:
    """Represent maintenance end dates as exclusive all-day events."""
    loaded_entry.runtime_data.park_info_coordinator.async_set_updated_data(
        {
            "OpeningHours": [],
            "Maintenance": [
                {
                    "DateFrom": "2026-11-20T00:00:00",
                    "DateTo": "2026-11-23T00:00:00",
                    "Name": "Baron 1898",
                    "OpenInWeekend": False,
                    "Type": "attraction",
                    "Url": "/nl/park/attracties/baron-1898",
                }
            ],
            "Events": [],
        }
    )
    await hass.async_block_till_done()

    registry_entry = entity_registry_entry(
        loaded_entry,
        "maintenance",
    )
    calendar = _get_calendar(hass, registry_entry.entity_id)

    events = await calendar.async_get_events(
        hass,
        datetime(2026, 11, 20, 0, 0, tzinfo=PARK_TIME_ZONE),
        datetime(2026, 11, 25, 0, 0, tzinfo=PARK_TIME_ZONE),
    )

    assert len(events) == 1
    event = events[0]
    assert "Baron 1898" in event.summary
    assert event.start == date(2026, 11, 20)
    assert event.end == date(2026, 11, 23)
    assert event.description is None


async def test_show_schedule_calendar(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    entity_registry_entry: Callable[[MockConfigEntry, str], RegistryEntry],
) -> None:
    """Include current and future performances, ignoring invalid entries."""
    wait_times = dict(loaded_entry.runtime_data.wait_times_coordinator.data)
    wait_times["aquanura"] = {
        "Id": "aquanura",
        "Name": "Aquanura",
        "State": "open",
        "ShowTimes": [
            {
                "StartDateTime": "2026-11-20T19:15:00+01:00",
                "EndDateTime": "2026-11-20T19:27:00+01:00",
                "Duration": 12,
                "Edition": "Matinee",
            },
            {
                "StartDateTime": "2026-11-20T20:15:00+01:00",
                "Duration": 12,
                "Edition": "Evening",
            },
            {
                "StartDateTime": "invalid",
                "EndDateTime": "invalid",
            },
        ],
        "PastShowTimes": [
            {
                "StartDateTime": "2026-11-20T18:15:00+01:00",
                "EndDateTime": "2026-11-20T18:27:00+01:00",
            }
        ],
    }

    loaded_entry.runtime_data.wait_times_coordinator.async_set_updated_data(wait_times)
    await hass.async_block_till_done()

    registry_entry = entity_registry_entry(loaded_entry, "shows")
    calendar = _get_calendar(hass, registry_entry.entity_id)
    tz = PARK_TIME_ZONE
    events = await calendar.async_get_events(
        hass,
        datetime(2026, 11, 20, 19, 0, tzinfo=tz),
        datetime(2026, 11, 20, 21, 0, tzinfo=tz),
    )

    assert len(events) == 2
    first, second = events
    assert first.summary == "Aquanura"
    assert isinstance(first.start, datetime)
    assert isinstance(first.end, datetime)
    assert first.start.astimezone(tz) == datetime(2026, 11, 20, 19, 15, tzinfo=tz)
    assert first.end.astimezone(tz) == datetime(2026, 11, 20, 19, 27, tzinfo=tz)
    assert first.description is not None
    assert "Matinee" in first.description
    assert second.summary == "Aquanura"
    assert isinstance(second.start, datetime)
    assert isinstance(second.end, datetime)
    assert second.start.astimezone(tz) == datetime(2026, 11, 20, 20, 15, tzinfo=tz)
    assert second.end.astimezone(tz) == datetime(2026, 11, 20, 20, 27, tzinfo=tz)


async def test_annual_pass_restrictions_calendar(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    entity_registry_entry: Callable[[MockConfigEntry, str], RegistryEntry],
) -> None:
    """Combine consecutive unavailable dates into all-day events."""
    loaded_entry.runtime_data.annual_passes_coordinator.async_set_updated_data(
        {
            "2026-11-20": {"Classic": False, "Plus": True, "Premium": True},
            "2026-11-21": {"Classic": False, "Plus": True, "Premium": True},
            "2026-11-22": {"Classic": True, "Plus": True, "Premium": True},
            "2026-11-23": {"Classic": None, "Plus": True, "Premium": True},
            "2026-11-24": {"Classic": False, "Plus": True, "Premium": True},
            "2026-11-25": {"Classic": True, "Plus": False, "Premium": True},
        }
    )
    await hass.async_block_till_done()

    registry_entry = entity_registry_entry(
        loaded_entry,
        "annual_pass_classic_blackout_dates",
    )
    calendar = _get_calendar(hass, registry_entry.entity_id)
    events = await calendar.async_get_events(
        hass,
        datetime(2026, 11, 20, 0, 0, tzinfo=PARK_TIME_ZONE),
        datetime(2026, 11, 27, 0, 0, tzinfo=PARK_TIME_ZONE),
    )

    assert len(events) == 2
    assert events[0].start == date(2026, 11, 20)
    assert events[0].end == date(2026, 11, 22)
    assert events[1].start == date(2026, 11, 24)
    assert events[1].end == date(2026, 11, 25)

    plus_registry_entry = entity_registry_entry(
        loaded_entry,
        "annual_pass_plus_blackout_dates",
    )
    plus_calendar = _get_calendar(hass, plus_registry_entry.entity_id)
    plus_events = await plus_calendar.async_get_events(
        hass,
        datetime(2026, 11, 20, 0, 0, tzinfo=PARK_TIME_ZONE),
        datetime(2026, 11, 27, 0, 0, tzinfo=PARK_TIME_ZONE),
    )

    assert len(plus_events) == 1
    assert plus_events[0].start == date(2026, 11, 25)
    assert plus_events[0].end == date(2026, 11, 26)
