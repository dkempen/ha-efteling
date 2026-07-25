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


class EftelingPoiUpdateCoordinator(DataUpdateCoordinator[dict[str, Poi]]):
    """Coordinator that retrieves POI data and returns a mapping id -> poi fields."""

    config_entry: EftelingConfigEntry

    async def _async_update_data(self) -> dict[str, Poi]:
        """Fetch POI data and return a mapping of id -> POI fields (dict)."""
        try:
            poi_list: list[
                Poi
            ] = await self.config_entry.runtime_data.client.async_get_poi_list()

            poi_map: dict[str, Poi] = {}

            for poi in poi_list:
                # poi is a dict; keys may use "id" or "Id"
                poi_id_raw = poi.get("id") or poi.get("Id")
                if not poi_id_raw:
                    continue
                poi_id = str(poi_id_raw)
                poi_map[poi_id] = poi

                alternate_id_raw = poi.get("alternateid")
                if alternate_id_raw:
                    poi_map[str(alternate_id_raw)] = poi

        except EftelingApiClientAuthenticationError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except EftelingApiClientError as exception:
            raise UpdateFailed(exception) from exception
        else:
            return poi_map


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
