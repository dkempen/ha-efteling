"""Daily park schedule coordinator."""

from typing import TYPE_CHECKING

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from custom_components.efteling.api import (
    EftelingApiClientError,
)
from custom_components.efteling.models import ParkInfoResponse

if TYPE_CHECKING:
    from datetime import datetime

    from custom_components.efteling.data import EftelingConfigEntry


class EftelingParkInfoUpdateCoordinator(DataUpdateCoordinator[ParkInfoResponse]):
    """Retrieve park schedules for the current local month."""

    config_entry: EftelingConfigEntry

    async def _async_update_data(self) -> ParkInfoResponse:
        """Fetch park information using the current local year and month."""
        now: datetime = dt_util.now()
        try:
            return await self.config_entry.runtime_data.client.async_get_park_info(
                now.year, now.month
            )
        except EftelingApiClientError as exception:
            raise UpdateFailed(exception) from exception
