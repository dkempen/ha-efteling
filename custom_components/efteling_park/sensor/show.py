"""Show schedule sensor."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.util import dt as dt_util

from custom_components.efteling_park.const import (
    CUSTOM_SHOW_ICONS,
    PARK_TIME_ZONE,
    SHOWS,
)
from custom_components.efteling_park.coordinator import (
    EftelingWaitTimesCoordinator,
)
from custom_components.efteling_park.entity import EftelingEntity
from custom_components.efteling_park.show_utils import (
    parse_show_datetime,
    parse_show_duration,
)

from .utils import parse_poi_map_position, parse_poi_metadata

if TYPE_CHECKING:
    from collections.abc import Callable

    from custom_components.efteling_park.map import ParkMapMetadata
    from custom_components.efteling_park.models import Poi
    from custom_components.efteling_park.sensor.utils import (
        PoiMapPosition,
        PoiMetadata,
    )


@dataclass(frozen=True)
class ParsedShowTime:
    """Parsed showtime with timezone-normalized boundaries."""

    start: datetime
    end: datetime
    duration: int | None
    edition: str | None


ENTITY_DESCRIPTION_SHOW_START_TIME = SensorEntityDescription(
    key="show_start_time",
    translation_key="show_start_time",
    device_class=SensorDeviceClass.TIMESTAMP,
)


class EftelingShowSensor(
    EftelingEntity[EftelingWaitTimesCoordinator],
    SensorEntity,
):
    """Sensor for a single show. Native value is the active or next show start time."""

    def __init__(
        self,
        coordinator: EftelingWaitTimesCoordinator,
        show_id: str,
        show_name: str,
        poi: Poi,
        map_metadata: ParkMapMetadata | None = None,
    ) -> None:
        """Initialize show sensor."""
        super().__init__(
            coordinator,
            device_key=SHOWS,
            device_translation_key="efteling_shows",
        )
        self.entity_description = ENTITY_DESCRIPTION_SHOW_START_TIME
        self._show_id = show_id
        self._attr_unique_id = show_id
        self._attr_name = show_name
        self._unsub_timer: Callable[[], None] | None = None
        self.async_on_remove(self._cancel_timer)
        self._poi = poi
        self._map_metadata = map_metadata
        self._metadata: PoiMetadata = parse_poi_metadata(poi)
        self._map_position: PoiMapPosition = self._parse_map_position()
        self._poi_duration = parse_show_duration(poi.get("showduration"))
        self._entries: list[ParsedShowTime] = []
        self._refresh_entries()

    def _parse_map_position(self) -> PoiMapPosition:
        """Calculate map coordinates from the cached POI coordinates."""
        return parse_poi_map_position(
            self._metadata.latitude,
            self._metadata.longitude,
            self._poi.get("alternateid"),
            self._map_metadata,
            poi_id=self._show_id,
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to Home Assistant."""
        await super().async_added_to_hass()
        self._schedule_next_update()

    @callback
    def _cancel_timer(self) -> None:
        """Cancel the pending scheduled update."""
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._refresh_entries()
        super()._handle_coordinator_update()
        self._schedule_next_update()

    def update_poi(self, poi: Poi) -> None:
        """Refresh POI metadata, entity name, and map position."""
        if poi == self._poi:
            return

        self._poi = poi
        self._metadata = parse_poi_metadata(poi)
        self._map_position = self._parse_map_position()
        self._poi_duration = parse_show_duration(poi.get("showduration"))

        show = self.coordinator.data.get(self._show_id)
        self._attr_name = str(
            poi.get("name")
            or (show.get("Name") if show is not None else None)
            or self._show_id
        )

        self.async_write_ha_state()

    def update_map_metadata(self, metadata: ParkMapMetadata | None) -> None:
        """Recalculate only map-derived coordinates when map metadata changes."""
        if metadata == self._map_metadata:
            return

        self._map_metadata = metadata
        self._map_position = self._parse_map_position()
        self.async_write_ha_state()

    def _current_entry(self, now: datetime) -> ParsedShowTime | None:
        """Return the latest-starting show that is active at the given time."""
        return next(
            (item for item in reversed(self._entries) if item.start <= now < item.end),
            None,
        )

    def _refresh_entries(self) -> None:
        """Parse and sort show entries after coordinator data changes."""
        show = self.coordinator.data.get(self._show_id)

        if show is None:
            self._entries = []
            return

        entries: list[ParsedShowTime] = []

        for items in (show.get("ShowTimes"), show.get("PastShowTimes")):
            if items is None:
                continue

            for item in items:
                start = parse_show_datetime(item.get("StartDateTime"))

                if start is None:
                    continue

                end_raw = item.get("EndDateTime")
                end = parse_show_datetime(end_raw)
                duration = parse_show_duration(item.get("Duration"))

                if end is None and duration is not None:
                    end = start + timedelta(minutes=duration)

                if end is None or end <= start:
                    continue

                entries.append(
                    ParsedShowTime(
                        start=start,
                        end=end,
                        duration=duration,
                        edition=item.get("Edition"),
                    )
                )

        self._entries = sorted(entries, key=lambda item: item.start)

    def _schedule_next_update(self) -> None:
        """Schedule the next show, show-end, or Efteling-local midnight update."""
        self._cancel_timer()

        now = dt_util.now()
        park_now = now.astimezone(PARK_TIME_ZONE)
        current = self._current_entry(now)

        next_midnight = park_now.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        ) + timedelta(days=1)

        boundaries = {item.start for item in self._entries if item.start > now}
        boundaries.add(next_midnight)

        if current is not None:
            boundaries.add(current.end)

        self._unsub_timer = async_track_point_in_time(
            self.hass,
            self._handle_scheduled_update,
            min(boundaries),
        )

    @callback
    def _handle_scheduled_update(self, _: datetime) -> None:
        """Handle the scheduled update event."""
        self._unsub_timer = None
        self.async_write_ha_state()
        self._schedule_next_update()

    @property
    def icon(self) -> str | None:
        """Return a show-specific icon when configured."""
        return CUSTOM_SHOW_ICONS.get(self._show_id)

    @property
    def native_value(self) -> datetime | None:
        """Return the start time of the current or next show."""
        now = dt_util.now()
        current = self._current_entry(now)

        if current is not None:
            return current.start

        return next((item.start for item in self._entries if item.start > now), None)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose showtimes and POI metadata, even without a schedule."""
        now = dt_util.now()
        entries = self._entries

        current = self._current_entry(now)
        future = [item for item in entries if item.start > now]
        today = now.astimezone(PARK_TIME_ZONE).date()
        future_today = [
            item
            for item in future
            if item.start.astimezone(PARK_TIME_ZONE).date() == today
        ]
        past = [item for item in entries if item.end <= now]

        source = (
            current or (future[0] if future else None) or (past[-1] if past else None)
        )

        status = (
            "current"
            if current
            else "upcoming"
            if future_today
            else "no_more_shows_today"
        )

        metadata = self._metadata
        map_position = self._map_position

        duration = (
            source.duration
            if source is not None and source.duration is not None
            else self._poi_duration
        )

        return {
            "id": self._show_id,
            "status": status,
            "current_show_end": current.end if current else None,
            "previous_showtimes": [item.start for item in past],
            "upcoming_showtimes": [item.start for item in future],
            "duration_minutes": duration,
            "edition": source.edition if source else None,
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
            "type": metadata.type,
            "sensor_type": "show_start_time",
        }
