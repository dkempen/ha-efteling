"""Efteling park map image entity."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.components.image import ImageEntity
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.util import dt as dt_util

from custom_components.efteling_park.binary_sensor.park_event import (
    is_park_event_active,
)
from custom_components.efteling_park.const import PARK, PARK_TIME_ZONE
from custom_components.efteling_park.coordinator import (
    EftelingParkInfoCoordinator,
)
from custom_components.efteling_park.entity import EftelingEntity
from custom_components.efteling_park.map import (
    MAP_IMAGE_URLS,
    MapSeason,
    ParkMapMetadata,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

    from custom_components.efteling_park.data import EftelingData


class EftelingParkMapImage(
    ImageEntity,
    EftelingEntity[EftelingParkInfoCoordinator],
):
    """Display the current seasonal Efteling park map."""

    _attr_translation_key = "map"
    _attr_unique_id = "park_map"
    _attr_content_type = "image/jpeg"

    def __init__(
        self,
        hass: HomeAssistant,
        data: EftelingData,
        map_metadata: ParkMapMetadata,
    ) -> None:
        """Initialize the park map image."""
        EftelingEntity.__init__(
            self,
            data.park_info_coordinator,
            device_key=PARK,
            device_translation_key="efteling_park",
        )
        ImageEntity.__init__(self, hass)

        self._hass = hass
        self._data = data
        self._map_metadata = map_metadata
        self._season: MapSeason = self._current_season()
        self._attr_image_last_updated = map_metadata.manifest[self._season]

        self._unsub_midnight: Callable[[], None] | None = None
        self.async_on_remove(self._cancel_midnight_update)

    @property
    def image_url(self) -> str:
        """Return the URL of the current seasonal map."""
        return MAP_IMAGE_URLS[self._season]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the geographic bounds and rotation of the map image."""
        attributes: dict[str, Any] = {}

        if self._map_metadata.bounds is not None:
            attributes.update(self._map_metadata.bounds)

        attributes["rotation_degrees"] = self._map_metadata.rotation_degrees

        return attributes

    async def async_added_to_hass(self) -> None:
        """Schedule seasonal map updates."""
        await super().async_added_to_hass()
        self._schedule_midnight_update()

    @callback
    def _current_season(self) -> MapSeason:
        """Return the season matching today's Winter Efteling event."""
        return "winter" if is_park_event_active(self._data, "winter") else "summer"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Invalidate the map cache if the selected season changed."""
        self._refresh_season()
        super()._handle_coordinator_update()

    @callback
    def _refresh_season(self) -> None:
        """Update the season and invalidate the cached image when needed."""
        season = self._current_season()

        if season != self._season:
            self._season = season
            self._cached_image = None
            self._attr_image_last_updated = self._map_metadata.manifest[season]

    @callback
    def _cancel_midnight_update(self) -> None:
        """Cancel the scheduled midnight update."""
        if self._unsub_midnight is not None:
            self._unsub_midnight()
            self._unsub_midnight = None

    @callback
    def _schedule_midnight_update(self) -> None:
        """Schedule a refresh at the next park-local midnight."""
        self._cancel_midnight_update()

        midnight = dt_util.now(PARK_TIME_ZONE).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

        self._unsub_midnight = async_track_point_in_time(
            self.hass,
            self._handle_midnight_update,
            midnight + timedelta(days=1),
        )

    @callback
    def _handle_midnight_update(self, _: datetime) -> None:
        """Refresh the selected map and schedule the next midnight update."""
        self._unsub_midnight = None
        self._refresh_season()
        self.async_write_ha_state()
        self._schedule_midnight_update()
