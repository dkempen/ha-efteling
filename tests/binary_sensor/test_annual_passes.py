"""Tests for Efteling annual pass binary sensors."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.util import dt as dt_util

from custom_components.efteling_park.const import PARK_TIME_ZONE

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant, State
    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant.common import MockConfigEntry


async def test_annual_pass_sensors_expose_all_dates(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    entity_registry_entry: Callable[[MockConfigEntry, str], er.RegistryEntry],
    entity_state: Callable[[str], State],
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
        entity = entity_registry_entry(loaded_entry, f"park_{tier}")
        state = entity_state(entity.entity_id)
        assert state.state == ("on" if expected else "off")
        assert state.attributes["annual_passes"] == {
            date: availability[pass_name] for date, availability in schedule.items()
        }


async def test_annual_pass_sensor_is_unavailable_without_today_data(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    entity_registry_entry: Callable[[MockConfigEntry, str], er.RegistryEntry],
    entity_state: Callable[[str], State],
) -> None:
    """Mark today's pass availability unavailable when Efteling omits its date."""
    entity = entity_registry_entry(loaded_entry, "park_classic")
    loaded_entry.runtime_data.annual_passes_coordinator.async_set_updated_data({})
    await hass.async_block_till_done()

    assert entity_state(entity.entity_id).state == "unavailable"
