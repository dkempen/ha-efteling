"""Custom types for Efteling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .api import EftelingApiClient
    from .coordinator.park_info import EftelingParkInfoUpdateCoordinator
    from .coordinator.poi import EftelingPoiUpdateCoordinator
    from .coordinator.wait_times import EftelingWaitTimesUpdateCoordinator


type EftelingConfigEntry = ConfigEntry[EftelingData]


@dataclass
class EftelingData:
    """Data for the Efteling integration."""

    client: EftelingApiClient
    poi_coordinator: EftelingPoiUpdateCoordinator
    wait_times_coordinator: EftelingWaitTimesUpdateCoordinator
    park_info_coordinator: EftelingParkInfoUpdateCoordinator
