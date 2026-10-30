"""Tests for Efteling binary sensor platforms."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from custom_components.efteling.api import EftelingApiClient
from custom_components.efteling.sensor import park_snapshot

if TYPE_CHECKING:
    import pytest
    from homeassistant.core import HomeAssistant, State
    from pytest_homeassistant_custom_component.common import MockConfigEntry


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


async def test_timer_callbacks_are_removed_when_entry_unloads(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    api_responses: None,
) -> None:
    """Unsubscribe coordinator and entity time listeners on unload."""
    del api_responses
    timer_removers = {
        name: MagicMock()
        for name in (
            "coordinator",
            "park_status",
            "park_event",
            "show",
            "park_sensor",
        )
    }
    show_start = dt_util.now() + timedelta(hours=1)
    show_end = show_start + timedelta(minutes=30)
    with (
        patch.object(
            EftelingApiClient,
            "async_get_wait_times",
            new_callable=AsyncMock,
            return_value=[
                {
                    "Id": "aquanura",
                    "Name": "Aquanura",
                    "State": "open",
                    "ShowTimes": [
                        {
                            "StartDateTime": show_start.isoformat(),
                            "EndDateTime": show_end.isoformat(),
                        }
                    ],
                }
            ],
        ),
        patch(
            "custom_components.efteling.coordinator.async_track_point_in_time",
            return_value=timer_removers["coordinator"],
        ),
        patch(
            "custom_components.efteling.binary_sensor.park_status.async_track_point_in_time",
            return_value=timer_removers["park_status"],
        ) as status_tracker,
        patch(
            "custom_components.efteling.binary_sensor.park_event.async_track_point_in_time",
            return_value=timer_removers["park_event"],
        ) as event_tracker,
        patch(
            "custom_components.efteling.sensor.show.async_track_point_in_time",
            return_value=timer_removers["show"],
        ) as show_tracker,
        patch(
            "custom_components.efteling.sensor.park.async_track_point_in_time",
            return_value=timer_removers["park_sensor"],
        ) as park_tracker,
    ):
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        for tracker in (
            status_tracker,
            event_tracker,
            show_tracker,
            park_tracker,
        ):
            for call in tracker.call_args_list.copy():
                call.args[1](call.args[2])
        await hass.async_block_till_done()

        cleanup_counts_before_unload = {
            name: remover.call_count for name, remover in timer_removers.items()
        }
        assert await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()

    assert all(
        remover.call_count > cleanup_counts_before_unload[name]
        for name, remover in timer_removers.items()
    )
