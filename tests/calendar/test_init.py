"""Tests for Efteling calendar platform setup."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers import entity_registry as er

from custom_components.efteling_park.const import DOMAIN

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant, State
    from homeassistant.helpers.entity_registry import RegistryEntry
    from pytest_homeassistant.common import MockConfigEntry


async def test_calendar_entities_are_registered(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Create all seven calendar entities."""
    registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(
        registry,
        loaded_entry.entry_id,
    )

    calendar_unique_ids = {
        entity.unique_id for entity in entries if entity.domain == "calendar"
    }

    assert calendar_unique_ids == {
        "opening_hours",
        "events",
        "maintenance",
        "shows",
        "annual_pass_classic_blackout_dates",
        "annual_pass_plus_blackout_dates",
        "annual_pass_premium_blackout_dates",
    }


async def test_replaced_event_calendars_are_removed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    api_responses: None,
) -> None:
    """Remove old event calendar registry entries when the entry is loaded."""
    del api_responses
    config_entry.add_to_hass(hass)
    registry = er.async_get(hass)
    replaced_entities = [
        registry.async_get_or_create(
            "calendar",
            DOMAIN,
            unique_id,
            config_entry=config_entry,
        )
        for unique_id in ("park_winter_efteling", "park_business_events")
    ]
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert all(
        registry.async_get(entity.entity_id) is None for entity in replaced_entities
    )
    assert any(
        entity.domain == "calendar" and entity.unique_id == "events"
        for entity in registry.entities.values()
    )


async def test_calendar_entities_have_distinct_translated_names(
    loaded_entry: MockConfigEntry,
    entity_registry_entry: Callable[[MockConfigEntry, str], RegistryEntry],
    entity_state: Callable[[str], State],
) -> None:
    """Expose the translated calendar name instead of only the device name."""
    expected_names = {
        "opening_hours": "Opening hours",
        "events": "Events",
        "maintenance": "Maintenance",
        "shows": "Shows",
        "annual_pass_classic_blackout_dates": "Classic annual pass blackout dates",
        "annual_pass_plus_blackout_dates": "Plus annual pass blackout dates",
        "annual_pass_premium_blackout_dates": "Premium annual pass blackout dates",
    }

    for unique_id, name in expected_names.items():
        entry = entity_registry_entry(loaded_entry, unique_id)
        friendly_name = entity_state(entry.entity_id).attributes["friendly_name"]
        assert friendly_name.endswith(name)
