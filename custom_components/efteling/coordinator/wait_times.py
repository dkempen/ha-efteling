"""Live attraction and show wait-time coordinator."""

from typing import TYPE_CHECKING

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from custom_components.efteling.api import EftelingApiClientError
from custom_components.efteling.models import AttractionInfo

if TYPE_CHECKING:
    from custom_components.efteling.data import EftelingConfigEntry


class EftelingWaitTimesUpdateCoordinator(
    DataUpdateCoordinator[dict[str, AttractionInfo]]
):
    """Retrieve wait-time entries indexed by attraction ID."""

    config_entry: EftelingConfigEntry

    async def _async_update_data(self) -> dict[str, AttractionInfo]:
        """Fetch wait times and index entries with IDs."""
        try:
            wait_times = (
                await self.config_entry.runtime_data.client.async_get_wait_times()
            )
        except EftelingApiClientError as exception:
            raise UpdateFailed(exception) from exception
        return {str(item["Id"]): item for item in wait_times if item.get("Id")}
