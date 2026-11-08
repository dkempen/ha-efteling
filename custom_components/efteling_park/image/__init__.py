"""Set up Efteling image entities."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .park_map import EftelingParkMapImage

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from custom_components.efteling_park.data import EftelingConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EftelingConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Efteling park map image."""
    runtime_data = entry.runtime_data

    if runtime_data.park_map is None:
        return

    async_add_entities(
        [
            EftelingParkMapImage(
                hass,
                runtime_data,
                runtime_data.park_map,
            )
        ]
    )
