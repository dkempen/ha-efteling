"""Custom types for Efteling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .api import EftelingApiClient
    from .coordinator import EftelingDataUpdateCoordinator


type EftelingConfigEntry = ConfigEntry[EftelingData]


@dataclass
class EftelingData:
    """Data for the Efteling integration."""

    client: EftelingApiClient
    coordinator: EftelingDataUpdateCoordinator
    integration: Integration
