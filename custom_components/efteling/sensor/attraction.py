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

from custom_components.efteling.const import (
    ATTRACTIONS,
    CUSTOM_ATTRACTION_ICONS,
)
from custom_components.efteling.coordinator import (
    EftelingWaitTimesUpdateCoordinator,
)
from custom_components.efteling.entity import EftelingEntity
from custom_components.efteling.models import ATTRACTION_STATUS_MAP, Poi

from .utils import parse_poi_metadata

ENTITY_DESCRIPTION_WAIT = SensorEntityDescription(
    key="wait_time",
    translation_key="wait_time",
    device_class=SensorDeviceClass.DURATION,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfTime.MINUTES,
    suggested_display_precision=0,
)


class EftelingAttractionSensor(
    EftelingEntity[EftelingWaitTimesUpdateCoordinator],
    SensorEntity,
):
    """Sensor for a single attraction."""

    def __init__(
        self,
        coordinator: EftelingWaitTimesUpdateCoordinator,
        attraction_id: str,
        attraction_name: str,
        poi: Poi,
    ) -> None:
        """Initialize sensor."""
        super().__init__(
            coordinator,
            device_key=ATTRACTIONS,
            device_translation_key="efteling_attractions",
        )
        self.entity_description = ENTITY_DESCRIPTION_WAIT
        self._attraction_id = attraction_id
        self._attr_unique_id = attraction_id
        self._attr_name = attraction_name
        self._poi = poi
        self._metadata = parse_poi_metadata(poi)

    def update_poi(self, poi: Poi) -> None:
        """Refresh cached metadata when the POI coordinator updates."""
        if poi is self._poi:
            return
        self._poi = poi
        self._metadata = parse_poi_metadata(poi)
        self.async_write_ha_state()

    @property
    def native_value(self) -> int | None:
        """Return wait time if attraction is open."""
        attraction = self.coordinator.data.get(self._attraction_id)
        if attraction is None or attraction.get("State") != "open":
            return None
        return attraction.get("WaitingTime")

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return attraction metadata and current status."""
        attraction = self.coordinator.data.get(self._attraction_id)
        if attraction is None:
            return None
        status = attraction["State"]
        metadata = self._metadata
        return {
            "empire": metadata.empire,
            "status": ATTRACTION_STATUS_MAP.get(status, status),
            "description": metadata.description,
            "subtitle": metadata.subtitle,
            "latitude": metadata.latitude,
            "longitude": metadata.longitude,
            "image": metadata.image,
            "image_detail": metadata.image_detail,
            "properties": metadata.properties,
            "entry_requirements": metadata.entry_requirements,
            "stimuli": metadata.stimuli,
            "targetgroups": metadata.targetgroups,
            "type": metadata.type,
        }

    @property
    def icon(self) -> str | None:
        """Return an attraction-specific icon when configured."""
        return CUSTOM_ATTRACTION_ICONS.get(self._attraction_id)
