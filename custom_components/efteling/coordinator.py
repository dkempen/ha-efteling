"""DataUpdateCoordinator for Efteling."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    EftelingApiClientAuthenticationError,
    EftelingApiClientError,
)

if TYPE_CHECKING:
    from .data import EftelingConfigEntry


class EftelingDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    config_entry: EftelingConfigEntry

    async def _async_update_data(self) -> Any:
        """Update data via library."""
        try:
            return await self.config_entry.runtime_data.client.async_get_wait_times()
        except EftelingApiClientAuthenticationError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except EftelingApiClientError as exception:
            raise UpdateFailed(exception) from exception
