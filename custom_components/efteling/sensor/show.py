"""Show schedule sensor."""

from __future__ import annotations

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
from custom_components.efteling.coordinator import EftelingWaitTimesUpdateCoordinator

from .utils import clean_html

if TYPE_CHECKING:
    from datetime import datetime

    from custom_components.efteling.models import Poi

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
        self._unsub_timer = None
        self._poi = poi

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to Home Assistant."""
        await super().async_added_to_hass()
        self._schedule_next_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        super()._handle_coordinator_update()
        self._schedule_next_update()

    def _get_entries(self) -> list[dict[str, Any]]:
        """Extract and sort all show entries."""
        show = self.coordinator.data.get(self._show_id)
        if show is None:
            return []
        entries: list[dict[str, Any]] = []
        for key in ("ShowTimes", "PastShowTimes"):
            raw = show.get(key)
            if not isinstance(raw, list):
                continue
            for item in raw:
                start_raw = item.get("StartDateTime")
                start = (
                    dt_util.parse_datetime(start_raw)
                    if isinstance(start_raw, str)
                    else None
                )
                if start is None:
                    continue
                end_raw = item.get("EndDateTime")
                end = (
                    dt_util.parse_datetime(end_raw)
                    if isinstance(end_raw, str)
                    else None
                )
                duration = item.get("Duration")
                try:
                    duration = int(duration) if duration is not None else None
                except TypeError, ValueError:
                    duration = None
                entries.append(
                    {
                        "start": dt_util.as_utc(start),
                        "end": dt_util.as_utc(end) if end else None,
                        "duration": duration,
                        "edition": item.get("Edition"),
                    }
                )
        entries.sort(key=lambda item: item["start"])
        return entries

    def _schedule_next_update(self) -> None:
        """Schedule an update at the next show boundary."""
        if self._unsub_timer:
            self._unsub_timer()
            self._unsub_timer = None
        now = dt_util.now()
        entries = self._get_entries()
        next_time: datetime | None = None
        for item in entries:
            if item["start"] <= now and (item["end"] is None or now < item["end"]):
                next_time = item["end"]
                break
            if item["start"] > now:
                next_time = item["start"]
                break
        if next_time:
            self._unsub_timer = async_track_point_in_time(
                self.hass, self._handle_scheduled_update, next_time
            )

    @callback
    def _handle_scheduled_update(self, _: datetime) -> None:
        """Handle the scheduled update event."""
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
        entries = self._get_entries()
        for item in entries:
            if item["start"] <= now and (item["end"] is None or now < item["end"]):
                return item["start"]
        return next((item["start"] for item in entries if item["start"] > now), None)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose current/upcoming showtimes and related metadata."""
        now = dt_util.now()
        entries = self._get_entries()
        if not entries:
            return None
        current = next(
            (
                item
                for item in entries
                if item["start"] <= now and (item["end"] is None or now < item["end"])
            ),
            None,
        )
        future = [item for item in entries if item["start"] > now]
        past = [item for item in entries if item["end"] and item["end"] <= now]
        source = (
            current or (future[0] if future else None) or (past[-1] if past else None)
        )
        status = (
            "current" if current else "upcoming" if future else "no_more_shows_today"
        )
        latitude, longitude = self._poi["latlon"].split(",", maxsplit=1)
        return {
            "status": status,
            "current_show_start": current["start"] if current else None,
            "current_show_end": current["end"] if current else None,
            "previous_showtimes": [item["start"] for item in past],
            "upcoming_showtimes": [item["start"] for item in future],
            "duration_minutes": source["duration"] if source else None,
            "edition": source["edition"] if source else None,
            "empire": self._poi["empire"],
            "description": clean_html(self._poi.get("detail_text", "")),
            "subtitle": self._poi.get("subtitle"),
            "latitude": float(latitude),
            "longitude": float(longitude),
            "image": f"https://www.efteling.com{self._poi['image']}",
            "image_detail": f"https://www.efteling.com{self._poi['image_detailview1']}",
            "properties": self._poi.get("properties"),
            "type": self._poi.get("type"),
        }
