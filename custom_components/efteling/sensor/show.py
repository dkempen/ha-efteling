"""Show schedule sensor."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from custom_components.efteling.const import CUSTOM_SHOW_ICONS, DOMAIN, NAME, SHOWS
from custom_components.efteling.coordinator.wait_times import (
    EftelingWaitTimesUpdateCoordinator,
)

from .utils import parse_poi_metadata

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from custom_components.efteling.models import Poi


@dataclass(frozen=True)
class ParsedShowTime:
    """Parsed showtime with timezone-normalized boundaries."""

    start: datetime
    end: datetime | None
    duration: int | None
    edition: str | None


ENTITY_DESCRIPTION_SHOW = SensorEntityDescription(
    key="start_time",
    translation_key="start_time",
    device_class=SensorDeviceClass.TIMESTAMP,
)


class EftelingShowSensor(
    CoordinatorEntity[EftelingWaitTimesUpdateCoordinator], SensorEntity
):
    """Sensor for a single show. Native value is the active or next show start time."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EftelingWaitTimesUpdateCoordinator,
        show_id: str,
        show_name: str,
        poi: Poi,
    ) -> None:
        """Initialize show sensor."""
        super().__init__(coordinator)
        self.entity_description = ENTITY_DESCRIPTION_SHOW
        self._show_id = show_id
        self._attr_unique_id = show_id
        self._attr_name = show_name
        self._unsub_timer: Callable[[], None] | None = None
        self.async_on_remove(self._cancel_timer)
        self._poi = poi
        self._metadata = parse_poi_metadata(poi)
        self._entries: list[ParsedShowTime] = []
        self._refresh_entries()

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to Home Assistant."""
        await super().async_added_to_hass()
        self._schedule_next_update()

    async def async_will_remove_from_hass(self) -> None:
        """Cancel scheduled callbacks when the entity is removed."""
        self._cancel_timer()
        await super().async_will_remove_from_hass()

    @callback
    def _cancel_timer(self) -> None:
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
        """Refresh cached metadata when the POI coordinator updates."""
        if poi is self._poi:
            return
        self._poi = poi
        self._metadata = parse_poi_metadata(poi)
        self.async_write_ha_state()

    def _refresh_entries(self) -> None:
        """Parse and sort show entries after coordinator data changes."""
        show = self.coordinator.data.get(self._show_id)
        if show is None:
            self._entries = []
            return
        entries: list[ParsedShowTime] = []
        for key in ("ShowTimes", "PastShowTimes"):
            for item in show.get(key, []):
                start = dt_util.parse_datetime(item["StartDateTime"])
                if start is None:
                    continue
                end_raw = item.get("EndDateTime")
                end = dt_util.parse_datetime(end_raw) if end_raw else None
                duration = item.get("Duration")
                if not isinstance(duration, int):
                    try:
                        duration = int(duration) if duration is not None else None
                    except TypeError, ValueError:
                        duration = None
                elif end is None:
                    end = start + timedelta(minutes=duration)
                if end is None:
                    continue
                entries.append(
                    ParsedShowTime(
                        start=dt_util.as_utc(start),
                        end=dt_util.as_utc(end) if end else None,
                        duration=duration,
                        edition=item.get("Edition"),
                    )
                )
        self._entries = sorted(entries, key=lambda item: item.start)

    def _schedule_next_update(self) -> None:
        """Schedule an update at the next show boundary."""
        if self._unsub_timer:
            self._unsub_timer()
            self._unsub_timer = None
        now = dt_util.now()
        entries = self._entries
        next_time: datetime | None = None
        active = next(
            (
                item
                for item in reversed(entries)
                if item.start <= now and (item.end is None or now < item.end)
            ),
            None,
        )
        if active is not None and active.end is not None:
            next_time = active.end
        else:
            next_time = next((item.start for item in entries if item.start > now), None)
        if next_time is not None:
            self._unsub_timer = async_track_point_in_time(
                self.hass, self._handle_scheduled_update, next_time
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
    def device_info(self) -> DeviceInfo:
        """Group all show sensors under one device."""
        return DeviceInfo(
            identifiers={(DOMAIN, SHOWS)},
            translation_key="efteling_shows",
            manufacturer=NAME,
        )

    @property
    def native_value(self) -> datetime | None:
        """Return the start time of the current or next show."""
        now = dt_util.now()
        for item in reversed(self._entries):
            if item.start <= now and (item.end is None or now < item.end):
                return item.start
        return next((item.start for item in self._entries if item.start > now), None)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose current/upcoming showtimes and related metadata."""
        now = dt_util.now()
        entries = self._entries
        if not entries:
            return None
        current = next(
            (
                item
                for item in reversed(entries)
                if item.start <= now and (item.end is None or now < item.end)
            ),
            None,
        )
        future = [item for item in entries if item.start > now]
        past = [item for item in entries if item.end is not None and item.end <= now]
        source = (
            current or (future[0] if future else None) or (past[-1] if past else None)
        )
        status = (
            "current" if current else "upcoming" if future else "no_more_shows_today"
        )
        metadata = self._metadata
        return {
            "status": status,
            "current_show_start": current.start if current else None,
            "current_show_end": current.end if current else None,
            "previous_showtimes": [item.start for item in past],
            "upcoming_showtimes": [item.start for item in future],
            "duration_minutes": source.duration if source else None,
            "edition": source.edition if source else None,
            "empire": metadata.empire,
            "description": metadata.description,
            "subtitle": metadata.subtitle,
            "latitude": metadata.latitude,
            "longitude": metadata.longitude,
            "image": metadata.image,
            "image_detail": metadata.image_detail,
            "properties": metadata.properties,
            "type": metadata.type,
        }
