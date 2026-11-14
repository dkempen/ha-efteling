"""Set up Efteling sensor entities."""

from __future__ import annotations

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

    from custom_components.efteling_park.data import EftelingConfigEntry
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
def _remove_status_sensors(hass: HomeAssistant, entry: EftelingConfigEntry) -> None:
    """Remove registered status sensors when status sensors are disabled."""
    registry = er.async_get(hass)

    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.domain == "sensor" and entity.unique_id.endswith("_status"):
            registry.async_remove(entity.entity_id)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EftelingConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities for attractions and shows."""
    runtime_data = entry.runtime_data

    known_ids: set[str] = set()
    entities: dict[str, list[EftelingAttractionSensor | EftelingShowSensor]] = {}

    create_status_sensors = entry.options.get(
        CONF_CREATE_ATTRACTION_STATUS_SENSORS,
        DEFAULT_CREATE_ATTRACTION_STATUS_SENSORS,
    )
    if not create_status_sensors:
        _remove_status_sensors(hass, entry)

    @callback
    def add_new_entities() -> None:
        wait_times = runtime_data.wait_times_coordinator.data
        poi_map = runtime_data.poi_coordinator.data
        sensors: list[SensorEntity] = []

        _update_poi_metadata(entities, poi_map)

        for attraction_id, attraction in wait_times.items():
            if attraction_id in known_ids:
                continue

            poi = poi_map.get(attraction_id)

            if poi is None:
                continue

            related_entities: list[EftelingAttractionSensor | EftelingShowSensor]
            entity: EftelingAttractionSensor | EftelingShowSensor

            if poi["category"] == "attraction":
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
                    coordinator=runtime_data.wait_times_coordinator,
                    attraction_id=attraction_id,
                    attraction_name=str(name),
                    poi=poi,
                    map_metadata=runtime_data.park_map,
                )
                sensors.append(entity)
                related_entities = [entity]

                if create_status_sensors:
                    status_sensor = EftelingAttractionStatusSensor(
                        coordinator=runtime_data.wait_times_coordinator,
                        attraction_id=attraction_id,
                        attraction_name=str(name),
                        poi=poi,
                        map_metadata=runtime_data.park_map,
                    )
                    sensors.append(status_sensor)
                    related_entities.append(status_sensor)

            elif poi["category"] == "show":
                name = poi["name"] or attraction["Name"] or attraction["Id"]

                entity = EftelingShowSensor(
                    coordinator=runtime_data.wait_times_coordinator,
                    show_id=attraction_id,
                    show_name=str(name),
                    poi=poi,
                    map_metadata=runtime_data.park_map,
                )
                sensors.append(entity)
                related_entities = [entity]

            else:
                continue

            known_ids.add(attraction_id)
            entities[attraction_id] = related_entities

        async_add_entities(sensors)

    add_new_entities()
    async_add_entities(create_park_sensors(runtime_data))

    entry.async_on_unload(
        runtime_data.wait_times_coordinator.async_add_listener(add_new_entities)
    )
    entry.async_on_unload(
        runtime_data.poi_coordinator.async_add_listener(add_new_entities)
    )
