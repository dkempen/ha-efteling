"""Tests for the Efteling park status binary sensor."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from custom_components.efteling_park.sensor import park_snapshot

if TYPE_CHECKING:
    from collections.abc import Callable

    import pytest
    from homeassistant.core import HomeAssistant, State
    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant.common import MockConfigEntry


async def test_missing_schedule_makes_park_status_unavailable(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    entity_registry_entry: Callable[[MockConfigEntry, str], er.RegistryEntry],
    entity_state: Callable[[str], State],
) -> None:
    """Distinguish a missing schedule from a valid closed day."""
    entity = entity_registry_entry(loaded_entry, "park_park_status")
    loaded_entry.runtime_data.park_info_coordinator.async_set_updated_data(
        {"OpeningHours": [], "Maintenance": [], "Events": []}
    )
    await hass.async_block_till_done()

    assert entity_state(entity.entity_id).state == "unavailable"


async def test_park_status_open_and_closed_boundaries(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    entity_registry_entry: Callable[[MockConfigEntry, str], er.RegistryEntry],
    entity_state: Callable[[str], State],
) -> None:
    """Report open within an interval and closed outside it."""
    now = datetime(2026, 10, 23, 12, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
    monkeypatch.setattr(park_snapshot.dt_util, "now", lambda _tz=None: now)
    entity = entity_registry_entry(loaded_entry, "park_park_status")
    schedule = {
        "Date": "2026-10-23",
        "OpeningHours": [{"Open": "10:00", "Close": "20:00"}],
    }
    loaded_entry.runtime_data.park_info_coordinator.async_set_updated_data(
        {"OpeningHours": [schedule], "Maintenance": [], "Events": []}
    )
    await hass.async_block_till_done()

    assert entity_state(entity.entity_id).state == "on"

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

    assert entity_state(entity.entity_id).state == "off"
