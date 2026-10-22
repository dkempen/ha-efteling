"""Set up Efteling binary sensor entities."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .park_event import create_park_event_binary_sensors
from .park_status import create_park_status_binary_sensor

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from custom_components.efteling.data import EftelingConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EftelingConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Efteling binary sensors."""
    del hass
    data = entry.runtime_data
    async_add_entities(
        [
            create_park_status_binary_sensor(data),
            *create_park_event_binary_sensors(data),
        ]
    )
