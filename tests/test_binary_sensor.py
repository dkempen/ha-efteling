"""Tests for Efteling binary sensor platforms."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from custom_components.efteling_park.const import PARK_TIME_ZONE
from custom_components.efteling_park.sensor import park_snapshot

if TYPE_CHECKING:
    import pytest
    from homeassistant.core import HomeAssistant, State
    from pytest_homeassistant.common import MockConfigEntry


def _entity_for_unique_id(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    unique_id: str,
) -> er.RegistryEntry:
    """Find a binary sensor registry entry owned by this config entry."""
    registry = er.async_get(hass)
    return next(
        entity
        for entity in registry.entities.values()
        if entity.config_entry_id == entry.entry_id and entity.unique_id == unique_id
    )


def _state(hass: HomeAssistant, entity_id: str) -> State:
    """Return the current state for a known entity ID."""
    state = hass.states.get(entity_id)
    if state is None:
        raise AssertionError
    return state


async def test_missing_schedule_makes_park_status_unavailable(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Distinguish a missing schedule from a valid closed day."""
    entity = _entity_for_unique_id(hass, loaded_entry, "park_park_status")
    loaded_entry.runtime_data.park_info_coordinator.async_set_updated_data(
        {"OpeningHours": [], "Maintenance": [], "Events": []}
    )
    await hass.async_block_till_done()
    assert _state(hass, entity.entity_id).state == "unavailable"


async def test_annual_pass_sensors_expose_all_dates(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Expose each pass tier's permission and every supplied date."""
    today = dt_util.now(PARK_TIME_ZONE).date()
    schedule = {
        (today + timedelta(days=offset)).isoformat(): {
            "Classic": offset != 0,
            "Plus": True,
            "Premium": offset != 1,
        }
        for offset in (0, 1, 30, 365)
    }
    loaded_entry.runtime_data.annual_passes_coordinator.async_set_updated_data(schedule)
    await hass.async_block_till_done()

    for tier, pass_name, expected in (
        ("classic", "Classic", False),
        ("plus", "Plus", True),
        ("premium", "Premium", True),
    ):
        entity = _entity_for_unique_id(hass, loaded_entry, f"park_{tier}")
        state = _state(hass, entity.entity_id)
        assert state.state == ("on" if expected else "off")
        assert state.attributes["annual_passes"] == {
            date: availability[pass_name] for date, availability in schedule.items()
        }


async def test_annual_pass_sensor_is_unavailable_without_today_data(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Mark today's pass availability unavailable when Efteling omits its date."""
    entity = _entity_for_unique_id(hass, loaded_entry, "park_classic")
    loaded_entry.runtime_data.annual_passes_coordinator.async_set_updated_data({})
    await hass.async_block_till_done()
    assert _state(hass, entity.entity_id).state == "unavailable"


async def test_park_status_open_and_closed_boundaries(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Report open within an interval and closed outside it."""
    now = datetime(2026, 10, 23, 12, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
    monkeypatch.setattr(park_snapshot.dt_util, "now", lambda _tz=None: now)
    entity = _entity_for_unique_id(hass, loaded_entry, "park_park_status")
    schedule = {
        "Date": "2026-10-23",
        "OpeningHours": [{"Open": "10:00", "Close": "20:00"}],
    }
    loaded_entry.runtime_data.park_info_coordinator.async_set_updated_data(
        {"OpeningHours": [schedule], "Maintenance": [], "Events": []}
    )
    await hass.async_block_till_done()
    assert _state(hass, entity.entity_id).state == "on"

    monkeypatch.setattr(
        park_snapshot.dt_util,
        "now",
        lambda _tz=None: datetime(
            2026, 10, 23, 21, 0, tzinfo=ZoneInfo("Europe/Amsterdam")
        ),
    )
    loaded_entry.runtime_data.park_info_coordinator.async_set_updated_data(
        {"OpeningHours": [schedule], "Maintenance": [], "Events": []}
    )
    await hass.async_block_till_done()
    assert _state(hass, entity.entity_id).state == "off"


async def test_event_sensors_expose_current_and_all_event_attributes(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Expose normalized event attributes and current-day binary states."""
    monkeypatch.setattr(
        park_snapshot.dt_util,
        "now",
        lambda _tz=None: datetime(
            2026, 10, 23, 12, 0, tzinfo=ZoneInfo("Europe/Amsterdam")
        ),
    )
    loaded_entry.runtime_data.park_info_coordinator.async_set_updated_data(
        {
            "OpeningHours": [{"Date": "2026-10-23", "OpeningHours": []}],
            "Maintenance": [],
            "Events": [
                {
                    "DateFrom": "2026-10-23",
                    "DateTo": "2026-10-23",
                    "Type": "winter",
                    "Name": "Winter",
                },
                {
                    "DateFrom": "2026-10-23",
                    "DateTo": "2026-10-23",
                    "Type": "business",
                    "Name": "(Bedrijfs)evenement",
                },
                {
                    "DateFrom": "2026-10-24",
                    "DateTo": "2026-10-25",
                    "Type": "winter",
                    "Name": "Future",
                },
            ],
        }
    )
    await hass.async_block_till_done()

    winter = _entity_for_unique_id(hass, loaded_entry, "park_winter_efteling")
    assert _state(hass, winter.entity_id).state == "on"
    winter_state = _state(hass, winter.entity_id)
    assert winter_state.attributes["current_winter_event"]["name"] == "Winter"
    assert len(winter_state.attributes["winter_events"]) == 2

    business = _entity_for_unique_id(hass, loaded_entry, "park_business_event")
    assert _state(hass, business.entity_id).state == "on"
    business_state = _state(hass, business.entity_id)
    assert (
        business_state.attributes["business_events_today"][0]["name"]
        == "(Bedrijfs)evenement"
    )
