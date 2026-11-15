"""Tests for Efteling sensor platform setup."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.efteling_park.api import EftelingApiClient
from custom_components.efteling_park.const import (
    ATTRACTIONS,
    CONF_CREATE_ATTRACTION_STATUS_SENSORS,
    DOMAIN,
    PARK,
    SHOWS,
)
from custom_components.efteling_park.sensor.park import PARK_SENSOR_DESCRIPTIONS

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant, State
    from pytest_homeassistant.common import MockConfigEntry


async def test_sensor_setup_preserves_entity_and_device_identity(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    entity_registry_entry: Callable[[MockConfigEntry, str], er.RegistryEntry],
) -> None:
    """Create attraction/show entities with their existing registry identities."""
    attraction = entity_registry_entry(loaded_entry, "python")
    show = entity_registry_entry(loaded_entry, "aquanura")
    park = entity_registry_entry(loaded_entry, "park_crowd_forecast")

    assert attraction.entity_id.startswith("sensor.")
    assert show.entity_id.startswith("sensor.")
    assert park.entity_id == "sensor.efteling_park_crowd_forecast"
    assert (
        len(
            [
                entity
                for entity in er.async_get(hass).entities.values()
                if entity.config_entry_id == loaded_entry.entry_id
                and entity.unique_id in {"python", "aquanura"}
            ]
        )
        == 2
    )
    assert attraction.entity_id == "sensor.efteling_attractions_python"
    assert show.entity_id == "sensor.efteling_shows_aquanura"
    assert not any(
        entity.config_entry_id == loaded_entry.entry_id
        and entity.unique_id == "python_status"
        for entity in er.async_get(hass).entities.values()
    )

    devices = dr.async_entries_for_config_entry(
        dr.async_get(hass),
        loaded_entry.entry_id,
    )
    identifiers = {
        identifier for device in devices for identifier in device.identifiers
    }
    assert (DOMAIN, ATTRACTIONS) in identifiers
    assert (DOMAIN, SHOWS) in identifiers
    assert (DOMAIN, PARK) in identifiers


async def test_attraction_status_sensor_is_created_when_enabled(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    api_responses: None,
    entity_registry_entry: Callable[[MockConfigEntry, str], er.RegistryEntry],
    entity_state: Callable[[str], State],
) -> None:
    """Create a filterable status sensor with the attraction's metadata."""
    del api_responses
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry,
        options={CONF_CREATE_ATTRACTION_STATUS_SENSORS: True},
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    wait_entity = entity_registry_entry(config_entry, "python")
    status_entity = entity_registry_entry(config_entry, "python_status")
    wait_state = entity_state(wait_entity.entity_id)
    status_state = entity_state(status_entity.entity_id)
    assert status_state.state == "open"
    assert status_state.attributes["sensor_type"] == "attraction_status"
    assert status_state.attributes["wait_time"] == 5
    assert "status" not in status_state.attributes
    assert wait_state.attributes["status"] == "open"
    assert wait_state.attributes["sensor_type"] == "attraction_wait_time"
    assert (
        status_state.attributes["description"] == wait_state.attributes["description"]
    )
    assert status_state.attributes["latitude"] == wait_state.attributes["latitude"]
    attraction_device = next(
        device
        for device in dr.async_entries_for_config_entry(
            dr.async_get(hass),
            config_entry.entry_id,
        )
        if (DOMAIN, ATTRACTIONS) in device.identifiers
    )
    assert attraction_device is not None
    assert status_entity.device_id == attraction_device.id


async def test_attraction_status_sensor_is_removed_when_disabled(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    api_responses: None,
    entity_registry_entry: Callable[[MockConfigEntry, str], er.RegistryEntry],
) -> None:
    """Remove registered status sensors after the option is disabled."""
    del api_responses
    config_entry.add_to_hass(hass)
    registry = er.async_get(hass)
    unrelated_status = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "unrelated_status",
        config_entry=config_entry,
    )
    hass.config_entries.async_update_entry(
        config_entry,
        options={CONF_CREATE_ATTRACTION_STATUS_SENSORS: True},
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    status_entity = entity_registry_entry(config_entry, "python_status")

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    hass.config_entries.async_update_entry(config_entry, options={})
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert not any(
        entity.config_entry_id == config_entry.entry_id
        and entity.unique_id == "python_status"
        for entity in er.async_get(hass).entities.values()
    )
    assert registry.async_get(unrelated_status.entity_id) is not None

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    hass.config_entries.async_update_entry(
        config_entry,
        options={CONF_CREATE_ATTRACTION_STATUS_SENSORS: True},
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    recreated_status = entity_registry_entry(config_entry, "python_status")
    assert recreated_status.entity_id == status_entity.entity_id


async def test_attraction_status_sensor_handles_missing_wait_data(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    api_responses: None,
    entity_registry_entry: Callable[[MockConfigEntry, str], er.RegistryEntry],
    entity_state: Callable[[str], State],
) -> None:
    """Mark the status unavailable when an update omits the attraction."""
    del api_responses
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry,
        options={CONF_CREATE_ATTRACTION_STATUS_SENSORS: True},
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    status_entity = entity_registry_entry(config_entry, "python_status")
    config_entry.runtime_data.wait_times_coordinator.async_set_updated_data({})
    await hass.async_block_till_done()

    assert entity_state(status_entity.entity_id).state == "unavailable"
    assert entity_registry_entry(config_entry, "python_status")


async def test_dynamic_sensor_creation_uses_names_and_ignores_unknown_pois(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    api_responses: None,
    entity_registry_entry: Callable[[MockConfigEntry, str], er.RegistryEntry],
) -> None:
    """Create only supported entities and preserve custom naming conventions."""
    del api_responses
    poi_records = [
        {
            "id": "stoomtreinm",
            "name": "Train fallback",
            "category": "attraction",
            "wis_info": {"Name": "Official train"},
        },
        {
            "id": "stoomtreinr",
            "name": "Railway fallback",
            "category": "attraction",
            "wis_info": {},
        },
        {
            "id": "alternate",
            "name": "Ride",
            "category": "attraction",
            "alternateid": "alternate",
            "alternatelabel": "Single Rider",
        },
        {
            "id": "alternate-mismatch",
            "name": "Mismatch Ride",
            "category": "attraction",
            "alternateid": "different-id",
            "alternatelabel": "Single Rider",
        },
        {"id": "unknown", "name": "Unknown", "category": "restaurant"},
    ]
    wait_records = [
        {"Id": "stoomtreinm", "Name": "Train", "State": "open", "WaitingTime": 5},
        {"Id": "stoomtreinr", "Name": "Railway", "State": "open", "WaitingTime": 5},
        {"Id": "alternate", "Name": "Ride", "State": "open", "WaitingTime": 10},
        {
            "Id": "alternate-mismatch",
            "Name": "Mismatch Ride",
            "State": "open",
            "WaitingTime": 10,
        },
        {"Id": "unknown", "Name": "Unknown", "State": "open", "WaitingTime": 1},
        {"Id": "missing-poi", "Name": "Missing", "State": "open", "WaitingTime": 1},
    ]
    with (
        patch.object(
            EftelingApiClient,
            "async_get_poi_list",
            new_callable=AsyncMock,
            return_value=poi_records,
        ),
        patch.object(
            EftelingApiClient,
            "async_get_wait_times",
            new_callable=AsyncMock,
            return_value=wait_records,
        ),
        patch.object(
            EftelingApiClient,
            "async_get_park_info",
            new_callable=AsyncMock,
            return_value={"OpeningHours": [], "Maintenance": [], "Events": []},
        ),
        patch.object(
            EftelingApiClient,
            "async_get_annual_passes",
            new_callable=AsyncMock,
            return_value={},
        ),
    ):
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    train = entity_registry_entry(config_entry, "stoomtreinm")
    railway = entity_registry_entry(config_entry, "stoomtreinr")
    alternate = entity_registry_entry(config_entry, "alternate")
    alternate_mismatch = entity_registry_entry(config_entry, "alternate-mismatch")
    assert train.original_name == "Official train"
    assert railway.original_name == "Railway fallback"
    assert alternate.original_name == "Ride Single Rider"
    assert alternate_mismatch.original_name == "Mismatch Ride"
    entity_ids = {
        entity.unique_id
        for entity in er.async_get(hass).entities.values()
        if entity.config_entry_id == config_entry.entry_id
    }
    assert "unknown" not in entity_ids
    assert "missing-poi" not in entity_ids


async def test_sensor_setup_without_supported_dynamic_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Set up Park sensors when the API has no dynamic entities to add."""
    with (
        patch.object(
            EftelingApiClient,
            "async_get_poi_list",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch.object(
            EftelingApiClient,
            "async_get_wait_times",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch.object(
            EftelingApiClient,
            "async_get_park_info",
            new_callable=AsyncMock,
            return_value={"OpeningHours": [], "Maintenance": [], "Events": []},
        ),
        patch.object(
            EftelingApiClient,
            "async_get_annual_passes",
            new_callable=AsyncMock,
            return_value={},
        ),
    ):
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    entity_ids = {
        entity.unique_id
        for entity in er.async_get(hass).entities.values()
        if entity.config_entry_id == config_entry.entry_id and entity.domain == "sensor"
    }
    assert entity_ids == {
        f"park_{description.key}" for description in PARK_SENSOR_DESCRIPTIONS
    }
