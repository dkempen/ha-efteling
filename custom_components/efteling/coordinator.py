"""DataUpdateCoordinator for Efteling."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from custom_components.efteling.models import AttractionInfo, Poi

from .api import (
    EftelingApiClientAuthenticationError,
    EftelingApiClientError,
)

if TYPE_CHECKING:
    from .data import EftelingConfigEntry


class EftelingPoiUpdateCoordinator(DataUpdateCoordinator[set[str]]):
    """Coordinator that retrieves POI attraction ids."""

    config_entry: EftelingConfigEntry

    async def _async_update_data(self) -> set[str]:
        """Fetch POI data and return attraction ids."""
        try:
            poi_list: list[
                Poi
            ] = await self.config_entry.runtime_data.client.async_get_poi_list()

            poi_ids: set[str] = set()

            for poi in poi_list:
                if "category" in poi and poi["category"] == "attraction":
                    poi_ids.add(poi["id"])

                    # Add alternateid if present (for single-rider variants)
                    alternate_id = poi.get("alternateid")
                    if alternate_id:
                        poi_ids.add(alternate_id)

        except EftelingApiClientAuthenticationError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except EftelingApiClientError as exception:
            raise UpdateFailed(exception) from exception
        else:
            return poi_ids


class EftelingWaitTimesUpdateCoordinator(DataUpdateCoordinator[list[AttractionInfo]]):
    """Class to manage fetching wait times data from the API."""

    config_entry: EftelingConfigEntry

    async def _async_update_data(self) -> list[AttractionInfo]:
        """Update wait times via library."""
        try:
            return await self.config_entry.runtime_data.client.async_get_wait_times()
        except EftelingApiClientAuthenticationError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except EftelingApiClientError as exception:
            raise UpdateFailed(exception) from exception
