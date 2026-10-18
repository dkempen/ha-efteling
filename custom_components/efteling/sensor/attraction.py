"""Attraction wait-time sensor."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.efteling.const import (
    ATTRACTIONS,
    CUSTOM_ATTRACTION_ICONS,
    DOMAIN,
    NAME,
)
from custom_components.efteling.coordinator import EftelingWaitTimesUpdateCoordinator
from custom_components.efteling.models import ATTRACTION_STATUS_MAP, Poi

from .utils import clean_html

ENTITY_DESCRIPTION_WAIT = SensorEntityDescription(
    key="wait_time",
    translation_key="wait_time",
    device_class=SensorDeviceClass.DURATION,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfTime.MINUTES,
    suggested_display_precision=0,
)


class EftelingAttractionSensor(
    CoordinatorEntity[EftelingWaitTimesUpdateCoordinator], SensorEntity
):
    """Sensor for a single attraction."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EftelingWaitTimesUpdateCoordinator,
        attraction_id: str,
        attraction_name: str,
        poi: Poi,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self.entity_description = ENTITY_DESCRIPTION_WAIT
        self._attraction_id = attraction_id
        self._attr_unique_id = attraction_id
        self._attr_name = attraction_name
        self._poi = poi

    @property
    def native_value(self) -> int | None:
        """Return wait time if attraction is open."""
        attraction = self.coordinator.data.get(self._attraction_id)
        if attraction is None or attraction["State"] != "open":
            return None
        wait_time = attraction.get("WaitingTime")
        if wait_time is None:
            return None
        try:
            return int(wait_time)
        except TypeError, ValueError:
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return attraction metadata and current status."""
        attraction = self.coordinator.data.get(self._attraction_id)
        if attraction is None:
            return None
        status = attraction["State"]
        status_str = str(status) if status is not None else ""
        latitude, longitude = self._poi["latlon"].split(",", maxsplit=1)
        return {
            "empire": self._poi["empire"],
            "status": ATTRACTION_STATUS_MAP.get(status_str, status_str),
            "description": clean_html(self._poi.get("detail_text", "")),
            "subtitle": self._poi.get("subtitle"),
            "latitude": float(latitude),
            "longitude": float(longitude),
            "image": f"https://www.efteling.com{self._poi['image']}",
            "image_detail": f"https://www.efteling.com{self._poi['image_detailview1']}",
            "properties": self._poi.get("properties"),
            "entry_requirements": self._poi.get("properties_entry_requirements"),
            "stimuli": self._poi.get("properties_stimuli"),
            "targetgroups": self._poi.get("targetgroups"),
            "type": self._poi.get("type"),
        }

    @property
    def icon(self) -> str | None:
        """Return an attraction-specific icon when configured."""
        return CUSTOM_ATTRACTION_ICONS.get(self._attraction_id)

    @property
    def device_info(self) -> DeviceInfo:
        """Group all attraction sensors under one device."""
        return DeviceInfo(
            identifiers={(DOMAIN, ATTRACTIONS)},
            translation_key="efteling_attractions",
            manufacturer=NAME,
        )
