"""Park forecast, schedule, and live crowd sensors."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.util import dt as dt_util

from custom_components.efteling.const import PARK, PARK_TIME_ZONE
from custom_components.efteling.coordinator import (
    EftelingParkInfoUpdateCoordinator,
)
from custom_components.efteling.entity import EftelingEntity
from custom_components.efteling.sensor.park_snapshot import (
    ParkSnapshot,
    as_records,
    build_snapshot,
    crowd_forecast_value,
    daily_crowd_forecasts,
    daily_occupancy_forecasts,
    occupancy_forecast_value,
    opening_hours_records,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from custom_components.efteling.data import EftelingData

CROWD_LEVELS = (
    (5, "very_quiet"),
    (10, "quiet"),
    (15, "fairly_quiet"),
    (20, "fairly_busy"),
    (25, "busy"),
    (30, "very_busy"),
    (float("inf"), "extremely_busy"),
)
LIVE_DATA_KEYS = frozenset({"average_wait_time", "crowd_level"})
TODAY_DATA_KEYS = frozenset(
    {"crowd_forecast", "occupancy_forecast", "opening_time", "closing_time"}
)


class EftelingParkSensor(
    EftelingEntity[EftelingParkInfoUpdateCoordinator],
    SensorEntity,
):
    """One sensor on the shared Efteling park device."""

    def __init__(
        self,
        coordinator: EftelingParkInfoUpdateCoordinator,
        data: EftelingData,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize a sensor for one Park metric."""
        super().__init__(
            coordinator,
            device_key=PARK,
            device_translation_key="efteling_park",
        )
        self.entity_description = description
        self._data = data
        self._attr_unique_id = f"park_{description.key}"
        self._unsub_timer: Callable[[], None] | None = None
        self.async_on_remove(self._cancel_timer)

    async def async_added_to_hass(self) -> None:
        """Subscribe to source coordinator and local-date updates."""
        await super().async_added_to_hass()

        if self.entity_description.key in LIVE_DATA_KEYS:
            for source in (
                self._data.poi_coordinator,
                self._data.wait_times_coordinator,
            ):
                remove_listener = source.async_add_listener(self._handle_source_update)
                self.async_on_remove(remove_listener)

        self._schedule_midnight_update()

    @callback
    def _handle_source_update(self) -> None:
        """Refresh the sensor when source data changes."""
        self.async_write_ha_state()

    @callback
    def _cancel_timer(self) -> None:
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None

    @callback
    def _schedule_midnight_update(self) -> None:
        """Schedule a refresh at the next Efteling-local midnight."""
        self._cancel_timer()
        now = dt_util.now(PARK_TIME_ZONE)
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        self._unsub_timer = async_track_point_in_time(
            self.hass,
            self._handle_scheduled_update,
            midnight + timedelta(days=1),
        )

    @callback
    def _handle_scheduled_update(self, _: datetime) -> None:
        """Refresh the sensor and schedule its next time-based update."""
        self._unsub_timer = None
        self.async_write_ha_state()
        self._schedule_midnight_update()

    def _snapshot(self) -> ParkSnapshot:
        """Return the current derived Park snapshot."""
        return build_snapshot(self._data)

    @property
    def available(self) -> bool:
        """Return whether all source data needed by this entity is available."""
        if not super().available:
            return False

        key = self.entity_description.key
        if key in LIVE_DATA_KEYS and not (
            self._data.poi_coordinator.last_update_success
            and self._data.wait_times_coordinator.last_update_success
        ):
            return False

        return key not in TODAY_DATA_KEYS or self._snapshot()["today"] is not None

    @property
    def native_value(self) -> str | int | float | datetime | None:
        """Return the current value for this Park metric."""
        snapshot = self._snapshot()
        key = self.entity_description.key
        today_record = snapshot["today"]
        value: str | int | float | datetime | None = None

        if key == "crowd_forecast":
            crowded = today_record.get("Crowded") if today_record else None
            value = crowd_forecast_value(crowded)

        elif key == "occupancy_forecast":
            occupancy = today_record.get("Crowdedness") if today_record else None
            value = occupancy_forecast_value(occupancy)

        elif key in ("opening_time", "closing_time"):
            value = snapshot[key]

        elif key == "attractions_under_maintenance":
            value = len(snapshot["maintenance_today"])

        elif key == "average_wait_time":
            value = snapshot["average_wait_time"]

        elif key == "crowd_level":
            average = snapshot["average_wait_time"]
            value = next(
                (
                    level
                    for threshold, level in CROWD_LEVELS
                    if average is not None and average < threshold
                ),
                None,
            )

        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose data related to this Park metric."""
        response = self.coordinator.data
        snapshot = self._snapshot()
        key = self.entity_description.key
        attributes: dict[str, Any] = {}

        if key in ("crowd_forecast", "occupancy_forecast"):
            if key == "crowd_forecast":
                attributes["daily_crowd_forecasts"] = daily_crowd_forecasts(
                    response["OpeningHours"]
                )
            else:
                attributes["daily_occupancy_forecasts"] = daily_occupancy_forecasts(
                    response["OpeningHours"]
                )

        elif key in ("opening_time", "closing_time"):
            attributes["opening_hours_today"] = opening_hours_records(
                [snapshot["today"]] if snapshot["today"] is not None else []
            )
            attributes["opening_hours_schedule"] = opening_hours_records(
                response["OpeningHours"]
            )

        elif key == "attractions_under_maintenance":
            attributes["maintenance_schedule"] = as_records(
                response["Maintenance"], exclude_keys={"State", "Type", "Url"}
            )
            attributes["maintenance_today"] = as_records(
                snapshot["maintenance_today"],
                exclude_keys={"State", "Type", "Url"},
            )
            attributes["maintenance_names"] = [
                name
                for item in snapshot["maintenance_today"]
                if (name := item.get("Name"))
            ]

        return attributes


PARK_SENSOR_DESCRIPTIONS = (
    SensorEntityDescription(
        key="crowd_forecast",
        translation_key="crowd_forecast",
        device_class=SensorDeviceClass.ENUM,
        options=["quiet", "normal", "busy"],
    ),
    SensorEntityDescription(
        key="occupancy_forecast",
        translation_key="occupancy_forecast",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="opening_time",
        translation_key="opening_time",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="closing_time",
        translation_key="closing_time",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="attractions_under_maintenance",
        translation_key="attractions_under_maintenance",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="average_wait_time",
        translation_key="average_wait_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="crowd_level",
        translation_key="crowd_level",
        device_class=SensorDeviceClass.ENUM,
        options=[level for _, level in CROWD_LEVELS],
    ),
)


def create_park_sensors(data: EftelingData) -> list[EftelingParkSensor]:
    """Create the Park metric sensors."""
    return [
        EftelingParkSensor(
            data.park_info_coordinator,
            data,
            description,
        )
        for description in PARK_SENSOR_DESCRIPTIONS
    ]
