"""Park open-status binary sensor."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from custom_components.efteling.const import DOMAIN, NAME, PARK
from custom_components.efteling.coordinator.park_info import (
    EftelingParkInfoUpdateCoordinator,
)
from custom_components.efteling.sensor.park_snapshot import (
    build_snapshot,
    opening_datetime,
    opening_hours_records,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from custom_components.efteling.data import EftelingData

PARK_STATUS_BINARY_SENSOR_DESCRIPTION = BinarySensorEntityDescription(
    key="park_status",
    translation_key="park_status",
    name=None,
)


class EftelingParkStatusBinarySensor(
    CoordinatorEntity[EftelingParkInfoUpdateCoordinator], BinarySensorEntity
):
    """Represent whether the Park is currently open."""

    _attr_has_entity_name = True

    def __init__(self, data: EftelingData) -> None:
        """Initialize the Park status binary sensor."""
        super().__init__(data.park_info_coordinator)
        self.entity_description = PARK_STATUS_BINARY_SENSOR_DESCRIPTION
        self._data = data
        self._attr_unique_id = "park_park_status"
        self._unsub_timer: Callable[[], None] | None = None
        self.async_on_remove(self._cancel_timer)

    async def async_added_to_hass(self) -> None:
        """Subscribe to source coordinator and opening-boundary updates."""
        await super().async_added_to_hass()
        for source in (
            self._data.poi_coordinator,
            self._data.wait_times_coordinator,
        ):
            self.async_on_remove(source.async_add_listener(self._handle_source_update))
        self._schedule_update()

    @callback
    def _handle_source_update(self) -> None:
        """Refresh when source data changes."""
        self.async_write_ha_state()

    @callback
    def _cancel_timer(self) -> None:
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None

    def _schedule_update(self) -> None:
        """Schedule a refresh at midnight or an opening-hours boundary."""
        self._cancel_timer()
        now = dt_util.now()
        boundaries = [
            now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        ]
        today = build_snapshot(self._data)["today"]
        if today is not None:
            boundaries.extend(
                boundary
                for interval in today.get("OpeningHours") or []
                for boundary in (
                    opening_datetime(today, interval.get("Open")),
                    opening_datetime(today, interval.get("Close")),
                )
                if boundary is not None and boundary > now
            )
        self._unsub_timer = async_track_point_in_time(
            self.hass, self._handle_scheduled_update, min(boundaries)
        )

    @callback
    def _handle_scheduled_update(self, _: datetime) -> None:
        """Refresh the entity and schedule its next time-based update."""
        self._unsub_timer = None
        self.async_write_ha_state()
        self._schedule_update()

    @property
    def is_on(self) -> bool:
        """Return whether the Park is currently open."""
        now = dt_util.now()
        today = build_snapshot(self._data)["today"]
        return today is not None and any(
            (opened := opening_datetime(today, interval.get("Open"))) is not None
            and (closed := opening_datetime(today, interval.get("Close"))) is not None
            and opened <= now < closed
            for interval in today.get("OpeningHours") or []
        )

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Expose today's opening intervals."""
        today = build_snapshot(self._data)["today"]
        return {
            "opening_hours_today": opening_hours_records(
                [today] if today is not None else []
            )
        }

    @property
    def device_info(self) -> DeviceInfo:
        """Return the shared Park device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, PARK)},
            translation_key="efteling_park",
            manufacturer=NAME,
        )


def create_park_status_binary_sensor(
    data: EftelingData,
) -> EftelingParkStatusBinarySensor:
    """Create the Park status binary sensor."""
    return EftelingParkStatusBinarySensor(data)
