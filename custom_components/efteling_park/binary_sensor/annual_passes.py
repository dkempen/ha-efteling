"""Annual-pass binary sensors."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.util import dt as dt_util

from custom_components.efteling_park.const import PARK, PARK_TIME_ZONE
from custom_components.efteling_park.coordinator import (
    EftelingAnnualPassesCoordinator,
)
from custom_components.efteling_park.entity import EftelingEntity

if TYPE_CHECKING:
    from collections.abc import Callable

    from custom_components.efteling_park.data import EftelingData

ANNUAL_PASS_DESCRIPTIONS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="classic",
        translation_key="annual_pass_classic",
    ),
    BinarySensorEntityDescription(
        key="plus",
        translation_key="annual_pass_plus",
    ),
    BinarySensorEntityDescription(
        key="premium",
        translation_key="annual_pass_premium",
    ),
)


class EftelingAnnualPassBinarySensor(
    EftelingEntity[EftelingAnnualPassesCoordinator],
    BinarySensorEntity,
):
    """Represent today's availability for one annual-pass tier."""

    def __init__(
        self,
        data: EftelingData,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize an annual-pass sensor."""
        super().__init__(
            data.annual_passes_coordinator,
            device_key=PARK,
            device_translation_key="efteling_park",
        )
        self.entity_description = description
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

    @callback
    def _schedule_midnight_update(self) -> None:
        """Schedule the next local-date update."""
        self._cancel_timer()
        midnight = dt_util.now(PARK_TIME_ZONE).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        self._unsub_timer = async_track_point_in_time(
            self.hass,
            self._handle_midnight,
            midnight + timedelta(days=1),
        )

    @callback
    def _handle_midnight(self, _: datetime) -> None:
        """Update the sensor for the new local date and schedule tomorrow."""
        self._unsub_timer = None
        self.async_write_ha_state()
        self._schedule_midnight_update()

    @property
    def _today_availability(self) -> bool | None:
        """Return today's availability for this tier, if present."""
        today = dt_util.now(PARK_TIME_ZONE).date().isoformat()
        schedule = self.coordinator.data.get(today)
        if schedule is None:
            return None
        return schedule.get(self.entity_description.key.title())

    @property
    def available(self) -> bool:
        """Return whether today's tier availability has been published."""
        return super().available and self._today_availability is not None

    @property
    def is_on(self) -> bool:
        """Return whether this pass tier is allowed today."""
        return self._today_availability is True

    @property
    def extra_state_attributes(self) -> dict[str, dict[str, bool | None]]:
        """Expose all annual-pass data for this tier."""
        schedule = {
            date: availability.get(self.entity_description.key.title())
            for date, availability in self.coordinator.data.items()
        }
        return {"annual_passes": schedule}


def create_annual_pass_binary_sensors(
    data: EftelingData,
) -> list[EftelingAnnualPassBinarySensor]:
    """Create one availability sensor for each annual-pass tier."""
    return [
        EftelingAnnualPassBinarySensor(data, description)
        for description in ANNUAL_PASS_DESCRIPTIONS
    ]
