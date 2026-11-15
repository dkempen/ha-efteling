"""Tests for Efteling attraction sensors."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from homeassistant.helpers import entity_registry as er

from custom_components.efteling_park.api import (
    EftelingApiClientCommunicationError,
)
from custom_components.efteling_park.const import (
    CONF_CREATE_ATTRACTION_STATUS_SENSORS,
)
from custom_components.efteling_park.sensor.attraction import EftelingAttractionSensor

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant, State
    from pytest_homeassistant.common import MockConfigEntry

    from custom_components.efteling_park.models import Poi
else:
    try:
        MockConfigEntry = import_module("pytest_homeassistant.common").MockConfigEntry
    except ModuleNotFoundError:
        MockConfigEntry = import_module(
            "pytest_homeassistant_custom_component.common"
        ).MockConfigEntry


async def test_new_and_disappearing_poi_entities(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    entity_registry_entry: Callable[[MockConfigEntry, str], er.RegistryEntry],
    entity_state: Callable[[str], State],
) -> None:
    """Create new entities and retain registry customizations across removal."""
    runtime_data = loaded_entry.runtime_data
    new_poi = {
        "id": "new_ride",
        "name": "New Ride",
        "category": "attraction",
        "detail_text": "A new attraction.",
    }
    new_wait_time = {
        "Id": "new_ride",
        "Name": "New Ride",
        "State": "open",
        "WaitingTime": 10,
    }
    poi_data = dict(runtime_data.poi_coordinator.data)
    poi_data["new_ride"] = new_poi
    runtime_data.poi_coordinator.async_set_updated_data(poi_data)
    await hass.async_block_till_done()

    wait_times = dict(runtime_data.wait_times_coordinator.data)
    wait_times["new_ride"] = new_wait_time
    runtime_data.wait_times_coordinator.async_set_updated_data(wait_times)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    entity = entity_registry_entry(loaded_entry, "new_ride")
    registry.async_update_entity(
        entity.entity_id,
        new_entity_id="sensor.custom_new_ride",
    )
    entity_id = "sensor.custom_new_ride"

    assert entity_state(entity_id).state == "10"

    poi_data.pop("new_ride")
    runtime_data.poi_coordinator.async_set_updated_data(poi_data)
    await hass.async_block_till_done()
    assert entity_state(entity_id).state == "unavailable"

    registered_entity = registry.async_get(entity_id)
    assert registered_entity is not None
    assert registered_entity.unique_id == "new_ride"

    poi_data["new_ride"] = new_poi
    runtime_data.poi_coordinator.async_set_updated_data(poi_data)
    await hass.async_block_till_done()
    assert entity_state(entity_id).state == "10"

    wait_times.pop("new_ride")
    runtime_data.wait_times_coordinator.async_set_updated_data(wait_times)
    await hass.async_block_till_done()
    assert entity_state(entity_id).state == "unavailable"

    registered_entity = registry.async_get(entity_id)
    assert registered_entity is not None
    assert registered_entity.unique_id == "new_ride"

    wait_times["new_ride"] = new_wait_time
    runtime_data.wait_times_coordinator.async_set_updated_data(wait_times)
    await hass.async_block_till_done()
    assert entity_state(entity_id).state == "10"

    poi_data["new_ride"] = {**new_poi, "category": "show"}
    runtime_data.poi_coordinator.async_set_updated_data(poi_data)
    await hass.async_block_till_done()
    state = entity_state(entity_id)
    assert state.state == "unknown"

    registered_entity = registry.async_get(entity_id)
    assert registered_entity is not None
    assert registered_entity.unique_id == "new_ride"


async def test_user_disabled_entity_stays_disabled_after_poi_reappears(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    entity_registry_entry: Callable[[MockConfigEntry, str], er.RegistryEntry],
) -> None:
    """Retain a user's disabled state when the corresponding POI disappears."""
    runtime_data = loaded_entry.runtime_data
    entity = entity_registry_entry(loaded_entry, "python")
    registry = er.async_get(hass)

    registry.async_update_entity(
        entity.entity_id,
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    await hass.async_block_till_done()

    poi_data = dict(runtime_data.poi_coordinator.data)
    python_poi = poi_data.pop("python")
    runtime_data.poi_coordinator.async_set_updated_data(poi_data)
    await hass.async_block_till_done()

    registered_entity = registry.async_get(entity.entity_id)
    assert registered_entity is not None
    assert registered_entity.disabled_by is er.RegistryEntryDisabler.USER

    poi_data["python"] = python_poi
    runtime_data.poi_coordinator.async_set_updated_data(poi_data)
    await hass.async_block_till_done()

    registered_entity = registry.async_get(entity.entity_id)
    assert registered_entity is not None
    assert registered_entity.disabled_by is er.RegistryEntryDisabler.USER
    assert registered_entity.unique_id == "python"
    assert hass.states.get(entity.entity_id) is None


async def test_attraction_state_metadata_and_wait_failure_recovery(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    entity_registry_entry: Callable[[MockConfigEntry, str], er.RegistryEntry],
    entity_state: Callable[[str], State],
) -> None:
    """Expose live wait and metadata, then become unavailable and recover."""
    runtime_data = loaded_entry.runtime_data
    entity = entity_registry_entry(loaded_entry, "python")
    state = entity_state(entity.entity_id)

    assert state.state == "5"
    assert state.attributes["description"].startswith("Zet je wereld")
    assert state.attributes["latitude"] == 51.647575

    updated_poi: Poi = runtime_data.poi_coordinator.data["python"].copy()
    updated_poi["name"] = "New Python"
    updated_poi["detail_text"] = "Updated <b>description</b>"
    updated_poi["latlon"] = "51.66,5.06"

    runtime_data.poi_coordinator.async_set_updated_data({"python": updated_poi})
    await hass.async_block_till_done()

    state = entity_state(entity.entity_id)
    assert state.attributes["friendly_name"].endswith("New Python")
    assert state.attributes["description"] == "Updated description"
    assert state.attributes["latitude"] == 51.66

    coordinator = runtime_data.wait_times_coordinator
    client_method = runtime_data.client.async_get_wait_times
    client_method.side_effect = EftelingApiClientCommunicationError("offline")

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert entity_state(entity.entity_id).state == "unavailable"

    client_method.side_effect = None
    client_method.return_value = [
        {"Id": "python", "Name": "Python", "State": "open", "WaitingTime": 0},
        {"Id": "aquanura", "Name": "Aquanura", "State": "open", "ShowTimes": []},
    ]

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    state = entity_state(entity.entity_id)
    assert state.state == "0"
    assert state.attributes["friendly_name"].endswith("New Python")


@pytest.mark.usefixtures("api_responses")
async def test_attraction_status_name_updates_with_poi(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry_entry: Callable[[MockConfigEntry, str], er.RegistryEntry],
    entity_state: Callable[[str], State],
) -> None:
    """Update the translated status sensor name when its POI name changes."""
    config_entry = MockConfigEntry(
        domain=config_entry.domain,
        title=config_entry.title,
        data=dict(config_entry.data),
        options={CONF_CREATE_ATTRACTION_STATUS_SENSORS: True},
        unique_id=config_entry.unique_id,
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    runtime_data = config_entry.runtime_data
    entity = entity_registry_entry(config_entry, "python_status")

    state = entity_state(entity.entity_id)
    assert state.attributes["friendly_name"].endswith("Python Status")

    updated_poi: Poi = runtime_data.poi_coordinator.data["python"].copy()
    updated_poi["name"] = "New Python"

    runtime_data.poi_coordinator.async_set_updated_data({"python": updated_poi})
    await hass.async_block_till_done()

    state = entity_state(entity.entity_id)
    assert state.attributes["friendly_name"].endswith("New Python Status")


async def test_attraction_ignores_equivalent_poi_replacements(
    loaded_entry: MockConfigEntry,
) -> None:
    """Avoid rewriting the entity when a refreshed POI has equal content."""
    runtime_data = loaded_entry.runtime_data
    poi: Poi = runtime_data.poi_coordinator.data["python"]
    sensor = EftelingAttractionSensor(
        coordinator=runtime_data.wait_times_coordinator,
        attraction_id="python",
        attraction_name="Python",
        poi=poi,
        map_metadata=runtime_data.park_map,
    )

    equivalent_poi: Poi = {**poi}
    changed_poi: Poi = {**poi, "detail_text": "Updated description"}

    with patch.object(sensor, "async_write_ha_state") as write_state:
        sensor.update_poi(equivalent_poi)
        write_state.assert_not_called()

        sensor.update_poi(changed_poi)
        write_state.assert_called_once()


async def test_attraction_closed_state_is_unknown_not_unavailable(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    entity_registry_entry: Callable[[MockConfigEntry, str], er.RegistryEntry],
    entity_state: Callable[[str], State],
) -> None:
    """Keep a successfully fetched closed attraction available with no value."""
    entity = entity_registry_entry(loaded_entry, "python")
    loaded_entry.runtime_data.wait_times_coordinator.async_set_updated_data(
        {
            "python": {
                "Id": "python",
                "Name": "Python",
                "State": "closed",
                "WaitingTime": None,
            }
        }
    )
    await hass.async_block_till_done()

    state = entity_state(entity.entity_id)
    assert state.state == "unknown"
