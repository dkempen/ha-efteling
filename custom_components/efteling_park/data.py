"""Custom types for Efteling."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

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
    park_map: ParkMapMetadata | None
    map_metadata_listeners: list[Callable[[ParkMapMetadata], None]] = field(
        default_factory=list
    )
