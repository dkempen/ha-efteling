"""Custom types for Efteling."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from homeassistant.core import callback

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.config_entries import ConfigEntry

    from .api import EftelingApiClient
    from .coordinator import (
        EftelingAnnualPassesCoordinator,
        EftelingMapMetadataCoordinator,
        EftelingParkInfoCoordinator,
        EftelingPoiCoordinator,
        EftelingWaitTimesCoordinator,
    )
    from .map import ParkMapMetadata


type EftelingConfigEntry = ConfigEntry[EftelingData]


@dataclass
class EftelingData:
    """Data for the Efteling integration."""

    client: EftelingApiClient
    poi_coordinator: EftelingPoiCoordinator
    wait_times_coordinator: EftelingWaitTimesCoordinator
    park_info_coordinator: EftelingParkInfoCoordinator
    annual_passes_coordinator: EftelingAnnualPassesCoordinator
    map_metadata_coordinator: EftelingMapMetadataCoordinator
    map_metadata_listeners: list[Callable[[ParkMapMetadata | None], None]] = field(
        default_factory=list,
    )

    def __post_init__(self) -> None:
        """Subscribe runtime listeners to validated metadata changes."""
        self._unsub_map_metadata = self.map_metadata_coordinator.async_add_listener(
            self._handle_map_metadata_update,
        )

    @property
    def park_map(self) -> ParkMapMetadata | None:
        """Return the most recently validated map metadata."""
        return self.map_metadata_coordinator.data

    @callback
    def _handle_map_metadata_update(self) -> None:
        """Notify map-dependent entities after metadata changes."""
        metadata = self.park_map
        for listener in tuple(self.map_metadata_listeners):
            listener(metadata)

    def unload(self) -> None:
        """Release listeners owned by runtime data."""
        self._unsub_map_metadata()
        self.map_metadata_listeners.clear()
