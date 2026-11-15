"""Tests for map coordinates exposed by Efteling sensors."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from custom_components.efteling_park.map import ParkMapMetadata

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant, State
    from pytest_homeassistant.common import MockConfigEntry


async def test_attraction_and_show_expose_map_coordinates(
    loaded_entry: MockConfigEntry,
    entity_state: Callable[[str], State],
) -> None:
    """Expose calculated map coordinates on attraction and show sensors."""
    map_metadata = loaded_entry.runtime_data.park_map
    assert map_metadata is not None

    for entity_id in (
        "sensor.efteling_attractions_python",
        "sensor.efteling_shows_aquanura",
    ):
        state = entity_state(entity_id)

        latitude = state.attributes["latitude"]
        longitude = state.attributes["longitude"]

        expected_position = map_metadata.map_position(latitude, longitude)
        assert expected_position is not None

        assert state.attributes["map_x"] == pytest.approx(expected_position[0])
        assert state.attributes["map_y"] == pytest.approx(expected_position[1])


async def test_attraction_and_show_recalculate_map_coordinates(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    entity_state: Callable[[str], State],
) -> None:
    """Recalculate map positions without changing API-derived POI metadata."""
    runtime_data = loaded_entry.runtime_data
    previous_metadata = runtime_data.park_map
    assert previous_metadata is not None

    updated_metadata = ParkMapMetadata(
        manifest=previous_metadata.manifest,
        bounds=previous_metadata.bounds,
        rotation_degrees=0,
    )
    runtime_data.map_metadata_coordinator.async_set_updated_data(updated_metadata)
    await hass.async_block_till_done()

    for entity_id in (
        "sensor.efteling_attractions_python",
        "sensor.efteling_shows_aquanura",
    ):
        state = entity_state(entity_id)

        expected = updated_metadata.map_position(
            state.attributes["latitude"],
            state.attributes["longitude"],
        )
        assert expected is not None
        assert state.attributes["map_x"] == pytest.approx(expected[0])
        assert state.attributes["map_y"] == pytest.approx(expected[1])

    attraction = entity_state("sensor.efteling_attractions_python")
    assert attraction.attributes["description"].startswith("Zet je wereld")

    show = entity_state("sensor.efteling_shows_aquanura")
    assert show.attributes["description"].startswith("Sluit je dag in de Efteling af")
