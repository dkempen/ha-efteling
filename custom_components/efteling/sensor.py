"""Sensor platform for Efteling."""

from __future__ import annotations

import html
import re
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from custom_components.efteling.const import (
    ATTRACTIONS,
    CUSTOM_ATTRACTION_ICONS,
    CUSTOM_SHOW_ICONS,
    DOMAIN,
    NAME,
    SHOWS,
    USE_ATTRACTION_INFO_NAME,
)
from custom_components.efteling.coordinator import EftelingWaitTimesUpdateCoordinator
from custom_components.efteling.models import ATTRACTION_STATE_MAP, Poi

if TYPE_CHECKING:
    from datetime import datetime

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from custom_components.efteling.data import EftelingConfigEntry


ENTITY_DESCRIPTION_WAIT = SensorEntityDescription(
    key="wait_time",
    device_class=SensorDeviceClass.DURATION,
    native_unit_of_measurement=UnitOfTime.MINUTES,
)

ENTITY_DESCRIPTION_SHOW = SensorEntityDescription(
    key="start_time",
    device_class=SensorDeviceClass.TIMESTAMP,
)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: EftelingConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities for attractions and shows."""
    runtime_data = entry.runtime_data

    wait_times_coordinator = runtime_data.wait_times_coordinator
    poi_coordinator = runtime_data.poi_coordinator

    poi_map: dict[str, Poi] = poi_coordinator.data
    attractions_and_shows = wait_times_coordinator.data

    sensors: list[SensorEntity] = []

    # Create attraction sensors
    for attraction in attractions_and_shows:
        attraction_id_raw = attraction["Id"]
        if not attraction_id_raw:
            continue

        attraction_id = str(attraction_id_raw)
        poi = poi_map.get(attraction_id)
        if poi and poi["category"] == "attraction":
            # Base name from poi, attraction, or fallback to ID
            name = poi["name"] or attraction["Name"] or attraction["Id"]

            # Override if the attraction should use attraction info name
            if attraction_id in USE_ATTRACTION_INFO_NAME:
                name = poi["wis_info"]["Name"]

            # Append alternate label if attraction id equals alternateid
            if poi.get("alternateid") and attraction_id == poi.get("alternateid"):
                name = f"{name} {poi.get('alternatelabel', '')}".strip()

            sensors.append(
                EftelingAttractionSensor(
                    coordinator=wait_times_coordinator,
                    description=ENTITY_DESCRIPTION_WAIT,
                    attraction_id=attraction_id,
                    attraction_name=str(name),
                    poi=poi,
                )
            )

    # Create show sensors
    for show in attractions_and_shows:
        show_id_raw = show["Id"]
        if not show_id_raw:
            continue

        show_id = str(show_id_raw)
        poi = poi_map.get(show_id)
        if poi and poi["category"] == "show":
            name = poi["name"] or show["Name"] or show["Id"]
            sensors.append(
                EftelingShowSensor(
                    coordinator=wait_times_coordinator,
                    description=ENTITY_DESCRIPTION_SHOW,
                    show_id=show_id,
                    show_name=str(name),
                    poi=poi,
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
        poi: Poi,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attraction_id = attraction_id
        self._attr_unique_id = attraction_id
        self._attr_name = attraction_name
        self._poi = poi

    @property
    def icon(self) -> str | None:
        """Return override icon if defined."""
        return CUSTOM_ATTRACTION_ICONS.get(
            self._attraction_id, self.entity_description.icon
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Group all sensors under one device."""
        return DeviceInfo(
            identifiers={(DOMAIN, ATTRACTIONS)},
            name=f"{NAME} {ATTRACTIONS}",
            manufacturer=NAME,
        )

    @property
    def native_value(self) -> int | None:
        """Return wait time if attraction is open."""
        attractions = self.coordinator.data or []

        for attraction in attractions:
            if attraction["Id"] == self._attraction_id:
                if attraction["State"] == "open" and "WaitingTime" in attraction:
                    try:
                        return int(attraction["WaitingTime"])
                    except TypeError, ValueError:
                        return None
                return None

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose empire and state as attributes and include full attraction object."""
        attractions = self.coordinator.data or []

        for attraction in attractions:
            if attraction["Id"] == self._attraction_id:
                state = attraction["State"]
                state_str = str(state) if state is not None else ""

                return {
                    "empire": self._poi["empire"],
                    "state": ATTRACTION_STATE_MAP.get(state_str, state_str),
                    "description": clean_html(self._poi.get("detail_text")),
                    "subtitle": self._poi.get("subtitle"),
                    "latitude": self._poi["latlon"].split(",")[0],
                    "longitude": self._poi["latlon"].split(",")[1],
                    "image": f"https://www.efteling.com{self._poi['image']}",
                    "image_detail": f"https://www.efteling.com{self._poi['image_detailview1']}",
                    "properties": self._poi.get("properties"),
                    "entry_requirements": self._poi.get(
                        "properties_entry_requirements"
                    ),
                    "stimuli": self._poi.get("properties_stimuli"),
                    "targetgroups": self._poi.get("targetgroups"),
                    "type": self._poi.get("type"),
                }

        return None


class EftelingShowSensor(
    CoordinatorEntity[EftelingWaitTimesUpdateCoordinator], SensorEntity
):
    """Sensor for a single show. Native value is the active or next show start time."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EftelingWaitTimesUpdateCoordinator,
        description: SensorEntityDescription,
        show_id: str,
        show_name: str,
        poi: Poi,
    ) -> None:
        """Initialize show sensor."""
        super().__init__(coordinator)
        self.entity_description = description
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
        """
        Extract all show entries.

        Returns a sorted list of dictionaries containing:
        start, end, duration, edition.
        """
        shows = self.coordinator.data or []

        for show in shows:
            if show["Id"] != self._show_id:
                continue

            entries: list[dict[str, Any]] = []

            for key in ("ShowTimes", "PastShowTimes"):
                raw = show.get(key)
                if not isinstance(raw, list):
                    continue

                for entry in raw:
                    start_raw = entry.get("StartDateTime")
                    start = (
                        dt_util.parse_datetime(start_raw)
                        if isinstance(start_raw, str)
                        else None
                    )
                    if not start:
                        continue

                    start = dt_util.as_utc(start)

                    end_raw = entry.get("EndDateTime")
                    end = (
                        dt_util.parse_datetime(end_raw)
                        if isinstance(end_raw, str)
                        else None
                    )
                    end = dt_util.as_utc(end) if end else None

                    duration = entry.get("Duration")
                    try:
                        duration = int(duration) if duration is not None else None
                    except TypeError, ValueError:
                        duration = None

                    entries.append(
                        {
                            "start": start,
                            "end": end,
                            "duration": duration,
                            "edition": entry.get("Edition"),
                        }
                    )

            entries.sort(key=lambda e: e["start"])
            return entries

        return []

    def _schedule_next_update(self) -> None:
        """
        Schedule a sensor update at the next show boundary.

        The sensor updates exactly when a show starts or ends,
        independent from the coordinator polling interval.
        """
        if self._unsub_timer:
            self._unsub_timer()
            self._unsub_timer = None

        now = dt_util.now()
        entries = self._get_entries()

        next_time: datetime | None = None

        for entry in entries:
            start = entry["start"]
            end = entry["end"]

            if start <= now and (end is None or now < end):
                next_time = end
                break

            if start > now:
                next_time = start
                break

        if next_time:
            self._unsub_timer = async_track_point_in_time(
                self.hass,
                self._handle_scheduled_update,
                next_time,
            )

    @callback
    def _handle_scheduled_update(self, _) -> None:  # noqa: ANN001
        """Handle the scheduled update event."""
        self.async_write_ha_state()
        self._schedule_next_update()

    @property
    def icon(self) -> str | None:
        """Override icon if defined for the show id, otherwise default icon."""
        return CUSTOM_SHOW_ICONS.get(self._show_id, self.entity_description.icon)

    @property
    def device_info(self) -> DeviceInfo:
        """Group show sensors under one device."""
        return DeviceInfo(
            identifiers={(DOMAIN, SHOWS)},
            name=f"{NAME} {SHOWS}",
            manufacturer=NAME,
        )

    @property
    def native_value(self) -> datetime | None:
        """Return the start time of the current or next show."""
        now = dt_util.now()
        entries = self._get_entries()

        for entry in entries:
            start = entry["start"]
            end = entry["end"]

            if start <= now and (end is None or now < end):
                return start

        for entry in entries:
            if entry["start"] > now:
                return entry["start"]

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose current/upcoming showtimes and related metadata."""
        now = dt_util.now()
        entries = self._get_entries()

        if not entries:
            return None

        current = next(
            (
                entry
                for entry in entries
                if entry["start"] <= now
                and (entry["end"] is None or now < entry["end"])
            ),
            None,
        )

        future = [entry for entry in entries if entry["start"] > now]
        past = [entry for entry in entries if entry["end"] and entry["end"] <= now]

        source = (
            current or (future[0] if future else None) or (past[-1] if past else None)
        )

        if current:
            state = "Nu bezig"
        elif future:
            state = "Binnenkort"
        else:
            state = "Geen shows meer vandaag"

        return {
            "state": state,
            "current_show_start": current["start"] if current else None,
            "current_show_end": current["end"] if current else None,
            "previous_showtimes": [e["start"] for e in past],
            "upcoming_showtimes": [e["start"] for e in future],
            "duration_minutes": source["duration"] if source else None,
            "edition": source["edition"] if source else None,
            "empire": self._poi["empire"],
            "description": clean_html(self._poi.get("detail_text")),
            "subtitle": self._poi.get("subtitle"),
            "latitude": self._poi["latlon"].split(",")[0],
            "longitude": self._poi["latlon"].split(",")[1],
            "image": f"https://www.efteling.com{self._poi['image']}",
            "image_detail": f"https://www.efteling.com{self._poi['image_detailview1']}",
            "properties": self._poi.get("properties"),
            "type": self._poi.get("type"),
        }


def clean_html(text: str) -> str:
    """Clean HTML tags from string."""
    text = html.unescape(text)
    text = re.sub(r"</p>\s*<p>", "\n\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()
