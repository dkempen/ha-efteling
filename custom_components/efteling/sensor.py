"""Sensor platform for Efteling."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfTime
from homeassistant.helpers.device_registry import DeviceInfo

from custom_components.efteling.const import CUSTOM_ICONS, DOMAIN, NAME

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from custom_components.efteling.data import EftelingConfigEntry

    from .coordinator import EftelingDataUpdateCoordinator


from typing import Any

from homeassistant.helpers.update_coordinator import CoordinatorEntity

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
    coordinator: EftelingDataUpdateCoordinator = entry.runtime_data.coordinator
    data = coordinator.data or {}
    attractions = data.get("AttractionInfo", [])

    sensors: list[EftelingAttractionSensor] = []

    for attr in attractions:
        if attr.get("Type") != "Attracties":
            continue

        attraction_id = attr.get("Id")
        attraction_name = attr.get("Name") or attraction_id

        sensors.append(
            EftelingAttractionSensor(
                coordinator=coordinator,
                description=ENTITY_DESCRIPTION,
                attraction_id=attraction_id,
                attraction_name=attraction_name,
            )
        )

    async_add_entities(sensors)


class EftelingAttractionSensor(CoordinatorEntity, SensorEntity):
    """Sensor for a single attraction."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EftelingDataUpdateCoordinator,
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
        """Return override icon if defined, otherwise default."""
        return CUSTOM_ICONS.get(self._attraction_id, self.entity_description.icon)

    @property
    def device_info(self) -> DeviceInfo:
        """Group all attraction sensors under one Efteling device."""
        return DeviceInfo(
            identifiers={(DOMAIN, DOMAIN)},
            name="Attracties",
            manufacturer=NAME,
        )

    @property
    def native_value(self) -> int | None:
        """Return wait time in minutes if attraction is open."""
        data = self.coordinator.data or {}
        attractions = data.get("AttractionInfo", [])

        for attr in attractions:
            if attr.get("Id") == self._attraction_id:
                if attr.get("State") == "open":
                    waiting_time = attr.get("WaitingTime")
                    if waiting_time is not None:
                        return int(waiting_time)
                return None

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose full attraction data as attributes."""
        data = self.coordinator.data or {}
        attractions = data.get("AttractionInfo", [])

        for attr in attractions:
            if attr.get("Id") == self._attraction_id:
                return dict(attr)

        return None
