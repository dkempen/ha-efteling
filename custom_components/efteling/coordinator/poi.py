"""POI data coordinator."""

from typing import TYPE_CHECKING

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from custom_components.efteling.api import EftelingApiClientError
from custom_components.efteling.models import Poi

if TYPE_CHECKING:
    from custom_components.efteling.data import EftelingConfigEntry


class EftelingPoiUpdateCoordinator(DataUpdateCoordinator[dict[str, Poi]]):
    """Retrieve POIs indexed by primary and alternate ID."""

    config_entry: EftelingConfigEntry

    async def _async_update_data(self) -> dict[str, Poi]:
        """Fetch POIs and index their IDs."""
        try:
            poi_list = await self.config_entry.runtime_data.client.async_get_poi_list()
        except EftelingApiClientError as exception:
            raise UpdateFailed(exception) from exception

        poi_map: dict[str, Poi] = {}
        for poi in poi_list:
            poi_map[poi["id"]] = poi
            alternate_id = poi.get("alternateid")
            if alternate_id:
                poi_map[alternate_id] = poi
        return poi_map
