"""Set up Efteling sensor entities."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.core import callback

from custom_components.efteling.const import USE_ATTRACTION_INFO_NAME

from .attraction import EftelingAttractionSensor
from .park import create_park_sensors
from .show import EftelingShowSensor

if TYPE_CHECKING:
    from homeassistant.components.sensor import SensorEntity
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from custom_components.efteling.data import EftelingConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EftelingConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities for attractions and shows."""
    del hass
    runtime_data = entry.runtime_data
    known_ids: set[str] = set()
    entities: dict[str, EftelingAttractionSensor | EftelingShowSensor] = {}

    @callback
    def add_new_entities() -> None:
        wait_times = runtime_data.wait_times_coordinator.data
        poi_map = runtime_data.poi_coordinator.data
        sensors: list[SensorEntity] = []

        for attraction_id, entity in entities.items():
            poi = poi_map.get(attraction_id)
            if poi is not None:
                entity.update_poi(poi)

        for attraction_id, attraction in wait_times.items():
            if attraction_id in known_ids:
                continue
            poi = poi_map.get(attraction_id)
            if poi is None:
                continue
            if poi["category"] == "attraction":
                name = poi["name"] or attraction["Name"] or attraction["Id"]
                if attraction_id in USE_ATTRACTION_INFO_NAME:
                    name = poi["wis_info"]["Name"]
                alternate_id = poi.get("alternateid")
                if alternate_id and attraction_id == alternate_id:
                    name = f"{name} {poi.get('alternatelabel', '')}".strip()
                entity = EftelingAttractionSensor(
                    coordinator=runtime_data.wait_times_coordinator,
                    attraction_id=attraction_id,
                    attraction_name=str(name),
                    poi=poi,
                )
                sensors.append(entity)
            elif poi["category"] == "show":
                name = poi["name"] or attraction["Name"] or attraction["Id"]
                entity = EftelingShowSensor(
                    coordinator=runtime_data.wait_times_coordinator,
                    show_id=attraction_id,
                    show_name=str(name),
                    poi=poi,
                )
                sensors.append(entity)
            else:
                continue
            known_ids.add(attraction_id)
            entities[attraction_id] = entity

        if sensors:
            async_add_entities(sensors)

    add_new_entities()
    async_add_entities(create_park_sensors(runtime_data))
    entry.async_on_unload(
        runtime_data.wait_times_coordinator.async_add_listener(add_new_entities)
    )
    entry.async_on_unload(
        runtime_data.poi_coordinator.async_add_listener(add_new_entities)
    )
