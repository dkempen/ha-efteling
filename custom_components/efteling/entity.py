"""Base entity for Efteling platforms."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from custom_components.efteling.const import DOMAIN, NAME


class EftelingEntity[CoordinatorT: DataUpdateCoordinator[Any]](
    CoordinatorEntity[CoordinatorT]
):
    """Base class for entities associated with an Efteling device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CoordinatorT,
        *,
        device_key: str,
        device_translation_key: str,
    ) -> None:
        """Initialize the entity and its shared device information."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_key)},
            translation_key=device_translation_key,
            manufacturer=NAME,
        )
