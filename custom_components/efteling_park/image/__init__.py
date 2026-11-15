"""Set up Efteling image entities."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.core import callback

from .park_map import EftelingParkMapImage

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from custom_components.efteling_park.data import EftelingConfigEntry
    from custom_components.efteling_park.map import ParkMapMetadata

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EftelingConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Efteling park map image."""
    runtime_data = entry.runtime_data

    @callback
    def add_map_image(metadata: ParkMapMetadata | None) -> None:
        """Add the image entity when valid map metadata becomes available."""
        if metadata is None:
            return

        remove_map_metadata_listener()
        async_add_entities([EftelingParkMapImage(hass, runtime_data, metadata)])

    @callback
    def remove_map_metadata_listener() -> None:
        """Remove the pending metadata listener."""
        if add_map_image in runtime_data.map_metadata_listeners:
            runtime_data.map_metadata_listeners.remove(add_map_image)

    if runtime_data.park_map is not None:
        add_map_image(runtime_data.park_map)
    else:
        runtime_data.map_metadata_listeners.append(add_map_image)
        entry.async_on_unload(remove_map_metadata_listener)
