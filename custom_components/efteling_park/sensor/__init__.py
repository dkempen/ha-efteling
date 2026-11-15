"""Set up Efteling sensor entities."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er

from custom_components.efteling_park.const import (
    CONF_CREATE_ATTRACTION_STATUS_SENSORS,
    DEFAULT_CREATE_ATTRACTION_STATUS_SENSORS,
    USE_ATTRACTION_INFO_NAME,
)

from .attraction import EftelingAttractionSensor, EftelingAttractionStatusSensor
from .park import create_park_sensors
from .show import EftelingShowSensor

if TYPE_CHECKING:
    from homeassistant.components.sensor import SensorEntity
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from custom_components.efteling_park.data import EftelingConfigEntry, EftelingData
    from custom_components.efteling_park.map import ParkMapMetadata
    from custom_components.efteling_park.models import Poi

PARALLEL_UPDATES = 0


def _update_poi_metadata(
    entities: dict[str, list[EftelingAttractionSensor | EftelingShowSensor]],
    poi_map: dict[str, Poi],
) -> None:
    """Update metadata for all entities associated with each POI."""
    for attraction_id, related_entities in entities.items():
        poi = poi_map.get(attraction_id)

        if poi is not None:
            for entity in related_entities:
                entity.update_poi(poi)


@callback
def _update_map_metadata(
    entities: dict[str, list[EftelingAttractionSensor | EftelingShowSensor]],
    metadata: ParkMapMetadata | None,
) -> None:
    """Recalculate map-derived attributes for all POI sensor entities."""
    for related_entities in entities.values():
        for entity in related_entities:
            entity.update_map_metadata(metadata)


def _register_map_metadata_listener(
    entry: EftelingConfigEntry,
    runtime_data: EftelingData,
    entities: dict[str, list[EftelingAttractionSensor | EftelingShowSensor]],
) -> None:
    """Register and clean up map metadata updates for POI sensors."""

    @callback
    def update_map_metadata(metadata: ParkMapMetadata | None) -> None:
        _update_map_metadata(entities, metadata)

    runtime_data.map_metadata_listeners.append(update_map_metadata)
    entry.async_on_unload(
        lambda: (
            runtime_data.map_metadata_listeners.remove(update_map_metadata)
            if update_map_metadata in runtime_data.map_metadata_listeners
            else None
        )
    )


@callback
def _remove_status_sensors(
    hass: HomeAssistant,
    entry: EftelingConfigEntry,
    poi_map: dict[str, Poi],
) -> None:
    """Remove registered status sensors when status sensors are disabled."""
    registry = er.async_get(hass)
    status_ids = {
        f"{poi_id}_status"
        for poi_id, poi in poi_map.items()
        if poi["category"] == "attraction"
    }

    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.domain == "sensor" and entity.unique_id in status_ids:
            registry.async_remove(entity.entity_id)


async def async_setup_entry(  # noqa: PLR0915 - Keep dynamic entity registration together.
    hass: HomeAssistant,
    entry: EftelingConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities for attractions and shows."""
    runtime_data = entry.runtime_data

    entities: dict[str, list[EftelingAttractionSensor | EftelingShowSensor]] = {}
    reconcile_lock = asyncio.Lock()

    create_status_sensors = entry.options.get(
        CONF_CREATE_ATTRACTION_STATUS_SENSORS,
        DEFAULT_CREATE_ATTRACTION_STATUS_SENSORS,
    )
    if not create_status_sensors:
        _remove_status_sensors(hass, entry, runtime_data.poi_coordinator.data)

    async def reconcile_entities() -> None:
        async with reconcile_lock:
            poi_coordinator = runtime_data.poi_coordinator
            wait_times_coordinator = runtime_data.wait_times_coordinator
            if (
                not poi_coordinator.last_update_success
                or not wait_times_coordinator.last_update_success
            ):
                return

            wait_times = wait_times_coordinator.data
            poi_map = poi_coordinator.data
            _update_poi_metadata(entities, poi_map)

            valid_categories = {
                attraction_id: poi_map[attraction_id]["category"]
                for attraction_id in wait_times.keys() & poi_map.keys()
                if poi_map[attraction_id]["category"] in {"attraction", "show"}
            }

            removed_ids = {
                attraction_id
                for attraction_id, related_entities in entities.items()
                if attraction_id not in valid_categories
                or (
                    valid_categories[attraction_id] == "attraction"
                    and not isinstance(related_entities[0], EftelingAttractionSensor)
                )
                or (
                    valid_categories[attraction_id] == "show"
                    and not isinstance(related_entities[0], EftelingShowSensor)
                )
            }
            for attraction_id in removed_ids:
                entities_to_remove = entities.pop(attraction_id)
                await asyncio.gather(
                    *(entity.async_remove() for entity in entities_to_remove)
                )

            sensors: list[SensorEntity] = []

            for attraction_id, category in valid_categories.items():
                if attraction_id in entities:
                    continue

                attraction = wait_times[attraction_id]
                poi = poi_map[attraction_id]

                related_entities: list[EftelingAttractionSensor | EftelingShowSensor]
                entity: EftelingAttractionSensor | EftelingShowSensor

                if category == "attraction":
                    name = poi["name"] or attraction["Name"] or attraction["Id"]

                    if attraction_id in USE_ATTRACTION_INFO_NAME:
                        wis_info = poi.get("wis_info")
                        wis_info_name = wis_info.get("Name") if wis_info else None

                        if wis_info_name and wis_info_name.strip():
                            name = wis_info_name.strip()

                    alternate_id = poi.get("alternateid")

                    if alternate_id and attraction_id == alternate_id:
                        name = f"{name} {poi.get('alternatelabel') or ''}".strip()

                    entity = EftelingAttractionSensor(
                        coordinator=wait_times_coordinator,
                        attraction_id=attraction_id,
                        attraction_name=str(name),
                        poi=poi,
                        map_metadata=runtime_data.park_map,
                    )
                    sensors.append(entity)
                    related_entities = [entity]

                    if create_status_sensors:
                        status_sensor = EftelingAttractionStatusSensor(
                            coordinator=wait_times_coordinator,
                            attraction_id=attraction_id,
                            attraction_name=str(name),
                            poi=poi,
                            map_metadata=runtime_data.park_map,
                        )
                        sensors.append(status_sensor)
                        related_entities.append(status_sensor)

                elif category == "show":
                    name = poi["name"] or attraction["Name"] or attraction["Id"]

                    entity = EftelingShowSensor(
                        coordinator=wait_times_coordinator,
                        show_id=attraction_id,
                        show_name=str(name),
                        poi=poi,
                        map_metadata=runtime_data.park_map,
                    )
                    sensors.append(entity)
                    related_entities = [entity]

                entities[attraction_id] = related_entities

            async_add_entities(sensors)

    @callback
    def schedule_reconciliation() -> None:
        entry.async_create_task(
            hass,
            reconcile_entities(),
            "efteling_sensor_entity_reconciliation",
        )

    await reconcile_entities()
    async_add_entities(create_park_sensors(runtime_data))

    entry.async_on_unload(
        runtime_data.wait_times_coordinator.async_add_listener(schedule_reconciliation)
    )
    entry.async_on_unload(
        runtime_data.poi_coordinator.async_add_listener(schedule_reconciliation)
    )

    _register_map_metadata_listener(entry, runtime_data, entities)
