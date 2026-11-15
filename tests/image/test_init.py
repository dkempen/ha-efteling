"""Tests for Efteling image platform setup."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from custom_components.efteling_park.image import async_setup_entry

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant.common import MockConfigEntry


async def test_image_setup_entry_parses_manifest(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Create the map image entity from runtime map metadata."""
    add_entities = MagicMock()
    await async_setup_entry(hass, loaded_entry, add_entities)

    add_entities.assert_called_once()
    assert len(add_entities.call_args.args[0]) == 1


async def test_image_setup_entry_waits_for_missing_map_metadata(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Register a listener and create the map image when metadata becomes available."""
    runtime_data = loaded_entry.runtime_data
    metadata = runtime_data.park_map
    assert metadata is not None

    runtime_data.map_metadata_coordinator.data = None
    listeners_before = tuple(runtime_data.map_metadata_listeners)
    add_entities = MagicMock()

    await async_setup_entry(hass, loaded_entry, add_entities)

    add_entities.assert_not_called()
    assert len(runtime_data.map_metadata_listeners) == len(listeners_before) + 1

    listener = next(
        item
        for item in runtime_data.map_metadata_listeners
        if item not in listeners_before
    )

    listener(None)
    add_entities.assert_not_called()

    runtime_data.map_metadata_coordinator.async_set_updated_data(metadata)
    await hass.async_block_till_done()

    add_entities.assert_called_once()
    assert len(add_entities.call_args.args[0]) == 1
    assert listener not in runtime_data.map_metadata_listeners
