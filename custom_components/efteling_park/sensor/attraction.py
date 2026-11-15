"""Attraction wait time sensor."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime

from custom_components.efteling_park.const import ATTRACTIONS, CUSTOM_ATTRACTION_ICONS
from custom_components.efteling_park.coordinator import (
    EftelingWaitTimesCoordinator,
)
from custom_components.efteling_park.entity import EftelingEntity
from custom_components.efteling_park.models import ATTRACTION_STATUS_MAP, Poi

from .utils import parse_poi_map_position, parse_poi_metadata

if TYPE_CHECKING:
    from custom_components.efteling_park.map import ParkMapMetadata
    from custom_components.efteling_park.sensor.utils import (
        PoiMapPosition,
        PoiMetadata,
    )

ENTITY_DESCRIPTION_ATTRACTION_WAIT_TIME = SensorEntityDescription(
    key="attraction_wait_time",
    translation_key="attraction_wait_time",
    device_class=SensorDeviceClass.DURATION,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfTime.MINUTES,
    suggested_display_precision=0,
)

ENTITY_DESCRIPTION_STATUS = SensorEntityDescription(
    key="attraction_status",
    translation_key="attraction_status",
    device_class=SensorDeviceClass.ENUM,
    options=sorted(set(ATTRACTION_STATUS_MAP.values()) | {"unknown"}),
)


class EftelingAttractionSensor(
    EftelingEntity[EftelingWaitTimesCoordinator],
    SensorEntity,
):
    """Sensor for a single attraction."""

    def __init__(
        self,
        coordinator: EftelingWaitTimesCoordinator,
        attraction_id: str,
        attraction_name: str,
        poi: Poi,
        map_metadata: ParkMapMetadata | None = None,
    ) -> None:
        """Initialize sensor."""
        super().__init__(
            coordinator,
            device_key=ATTRACTIONS,
            device_translation_key="efteling_attractions",
        )
        self.entity_description = ENTITY_DESCRIPTION_ATTRACTION_WAIT_TIME
        self._attraction_id = attraction_id
        self._attr_unique_id = attraction_id
        self._attr_name = attraction_name
        self._poi = poi
        self._map_metadata = map_metadata
        self._metadata: PoiMetadata = parse_poi_metadata(poi)
        self._map_position: PoiMapPosition = self._parse_map_position()

    def _parse_map_position(self) -> PoiMapPosition:
        """Calculate map coordinates from the cached POI coordinates."""
        return parse_poi_map_position(
            self._metadata.latitude,
            self._metadata.longitude,
            self._poi.get("alternateid"),
            self._map_metadata,
            poi_id=self._attraction_id,
        )

    def update_poi(self, poi: Poi) -> None:
        """Refresh POI metadata and its map position."""
        if poi == self._poi:
            return

        self._poi = poi
        self._metadata = parse_poi_metadata(poi)
        self._map_position = self._parse_map_position()
        self.async_write_ha_state()

    def update_map_metadata(self, metadata: ParkMapMetadata | None) -> None:
        """Recalculate only map-derived coordinates when map metadata changes."""
        if metadata == self._map_metadata:
            return

        self._map_metadata = metadata
        self._map_position = self._parse_map_position()
        self.async_write_ha_state()

    @property
    def native_value(self) -> int | str | None:
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

        return {
            **self._metadata_attributes(),
            "status": ATTRACTION_STATUS_MAP.get(
                attraction["State"], attraction["State"]
            ),
            "sensor_type": "attraction_wait_time",
        }

    def _metadata_attributes(self) -> dict[str, Any]:
        """Return the cached metadata shared by an attraction's sensors."""
        metadata = self._metadata
        map_position = self._map_position
        return {
            "id": self._attraction_id,
            "empire": metadata.empire,
            "description": metadata.description,
            "subtitle": metadata.subtitle,
            "latitude": metadata.latitude,
            "longitude": metadata.longitude,
            "map_x": map_position.map_x,
            "map_y": map_position.map_y,
            "map_marker": map_position.map_marker,
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


class EftelingAttractionStatusSensor(EftelingAttractionSensor):
    """Sensor for a single attraction's operating status."""

    def __init__(
        self,
        coordinator: EftelingWaitTimesCoordinator,
        attraction_id: str,
        attraction_name: str,
        poi: Poi,
        map_metadata: ParkMapMetadata | None = None,
    ) -> None:
        """Initialize the status sensor with the attraction's shared metadata."""
        super().__init__(
            coordinator,
            attraction_id,
            attraction_name,
            poi,
            map_metadata,
        )

        # Use the translated entity name instead of the inherited attraction name.
        del self._attr_name
        self._attr_translation_placeholders = {
            "attraction_name": attraction_name,
        }

        self.entity_description = ENTITY_DESCRIPTION_STATUS
        self._attr_unique_id = f"{attraction_id}_status"

    @property
    def icon(self) -> str | None:
        """Return an attraction-specific icon when configured."""
        return CUSTOM_ATTRACTION_ICONS.get(self._attraction_id)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return attraction metadata and its current wait time."""
        attraction = self.coordinator.data.get(self._attraction_id)
        if attraction is None:
            return None

        return {
            **self._metadata_attributes(),
            "wait_time": attraction.get("WaitingTime"),
            "map_marker": False,
            "sensor_type": "attraction_status",
        }

    @property
    def native_value(self) -> str | None:
        """Return the normalized operating status."""
        attraction = self.coordinator.data.get(self._attraction_id)

        if attraction is None:
            return None

        return ATTRACTION_STATUS_MAP.get(attraction["State"], "unknown")
