"""Sensor platform for Efteling."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfTime
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)

from custom_components.efteling.const import CUSTOM_ICONS, DOMAIN, NAME
from custom_components.efteling.coordinator import EftelingWaitTimesUpdateCoordinator
from custom_components.efteling.models import AttractionState

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from custom_components.efteling.data import EftelingConfigEntry, EftelingData

ENTITY_DESCRIPTION = SensorEntityDescription(
    key="wait_time",
    name="Wait Time",
    device_class=SensorDeviceClass.DURATION,
    native_unit_of_measurement=UnitOfTime.MINUTES,
)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: EftelingConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities for each attraction."""
    runtime_data: EftelingData = entry.runtime_data

    wait_coordinator = runtime_data.wait_times_coordinator
    poi_coordinator = runtime_data.poi_coordinator

    poi_ids: set[str] = poi_coordinator.data or set()

    attractions = wait_coordinator.data

    sensors: list[EftelingAttractionSensor] = []

    for attraction in attractions:
        # Only create sensors for POI attractions
        if attraction["Id"] not in poi_ids:
            continue

        sensors.append(
            EftelingAttractionSensor(
                coordinator=wait_coordinator,
                description=ENTITY_DESCRIPTION,
                attraction_id=attraction["Id"],
                attraction_name=attraction["Name"],
            )
        )

    async_add_entities(sensors)


class EftelingAttractionSensor(
    CoordinatorEntity[EftelingWaitTimesUpdateCoordinator], SensorEntity
):
    """Sensor for a single attraction."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EftelingWaitTimesUpdateCoordinator,
        description: SensorEntityDescription,
        attraction_id: str,
        attraction_name: str,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attraction_id = attraction_id
        self._attr_unique_id = attraction_id
        self._attr_name = attraction_name

    @property
    def icon(self) -> str | None:
        """Return override icon if defined."""
        return CUSTOM_ICONS.get(self._attraction_id, self.entity_description.icon)

    @property
    def device_info(self) -> DeviceInfo:
        """Group all sensors under one device."""
        return DeviceInfo(
            identifiers={(DOMAIN, DOMAIN)},
            name="Attracties",
            manufacturer=NAME,
        )

    @property
    def native_value(self) -> int | None:
        """Return wait time if attraction is open."""
        attractions = self.coordinator.data

        for attraction in attractions:
            if attraction["Id"] == self._attraction_id:
                if attraction["State"] == "open" and "WaitingTime" in attraction:
                    return int(attraction["WaitingTime"])
                return None

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose empire and state as attributes."""
        attractions = self.coordinator.data

        for attraction in attractions:
            if attraction["Id"] == self._attraction_id:
                return {
                    "empire": attraction["Empire"],
                    "state": AttractionState[attraction["State"] or "gesloten"].value,
                }

        return None
