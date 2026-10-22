"""Park special-event binary sensors."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from custom_components.efteling.const import DOMAIN, NAME, PARK, PARK_TIME_ZONE
from custom_components.efteling.coordinator.park_info import (
    EftelingParkInfoUpdateCoordinator,
)
from custom_components.efteling.sensor.park_snapshot import as_records, build_snapshot

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from custom_components.efteling.data import EftelingData

PARK_EVENT_BINARY_SENSOR_DESCRIPTIONS = (
    BinarySensorEntityDescription(
        key="winter_efteling",
        translation_key="winter_efteling",
    ),
    BinarySensorEntityDescription(
        key="business_event",
        translation_key="business_event",
    ),
)


class EftelingParkEventBinarySensor(
    CoordinatorEntity[EftelingParkInfoUpdateCoordinator], BinarySensorEntity
):
    """Represent whether a special event is active today."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EftelingParkInfoUpdateCoordinator,
        data: EftelingData,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize an event binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._data = data
        self._attr_unique_id = f"park_{description.key}"
        self._unsub_timer: Callable[[], None] | None = None
        self.async_on_remove(self._cancel_timer)

    async def async_added_to_hass(self) -> None:
        """Subscribe to local-date updates."""
        await super().async_added_to_hass()
        self._schedule_midnight_update()

    @callback
    def _cancel_timer(self) -> None:
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None

    def _schedule_midnight_update(self) -> None:
        """Schedule a refresh at the next local midnight."""
        self._cancel_timer()
        midnight = dt_util.now(PARK_TIME_ZONE).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        self._unsub_timer = async_track_point_in_time(
            self.hass, self._handle_midnight, midnight + timedelta(days=1)
        )

    @callback
    def _handle_midnight(self, _: datetime) -> None:
        """Refresh the entity and schedule the next day's update."""
        self._unsub_timer = None
        self.async_write_ha_state()
        self._schedule_midnight_update()

    @property
    def is_on(self) -> bool:
        """Return whether the corresponding event is active today."""
        event_type = {
            "winter_efteling": "winter",
            "business_event": "business",
        }[self.entity_description.key]
        return any(
            item.get("Type") == event_type
            for item in build_snapshot(self._data)["events_today"]
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the relevant event schedule."""
        response = self.coordinator.data
        events_today = build_snapshot(self._data)["events_today"]
        event_type = {
            "winter_efteling": "winter",
            "business_event": "business",
        }[self.entity_description.key]
        all_matching_events = [
            item for item in response["Events"] if item.get("Type") == event_type
        ]
        matching_today = [
            item for item in events_today if item.get("Type") == event_type
        ]
        if event_type == "business":
            return {
                "business_events_today": as_records(matching_today),
                "business_events": as_records(all_matching_events),
            }
        normalized_events = as_records(all_matching_events)
        normalized_today = as_records(matching_today)
        return {
            "current_winter_event": normalized_today[0] if normalized_today else None,
            "winter_events": normalized_events,
        }

    @property
    def device_info(self) -> DeviceInfo:
        """Return the shared Park device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, PARK)},
            translation_key="efteling_park",
            manufacturer=NAME,
        )


def create_park_event_binary_sensors(
    data: EftelingData,
) -> list[EftelingParkEventBinarySensor]:
    """Create the special-event binary sensors."""
    return [
        EftelingParkEventBinarySensor(data.park_info_coordinator, data, description)
        for description in PARK_EVENT_BINARY_SENSOR_DESCRIPTIONS
    ]
