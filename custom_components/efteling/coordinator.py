"""Data update coordinators for Efteling."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from custom_components.efteling.api import (
    EftelingApiClient,
    EftelingApiClientError,
)
from custom_components.efteling.const import DOMAIN, LOGGER, PARK_TIME_ZONE
from custom_components.efteling.models import (
    AttractionInfo,
    ParkInfoResponse,
    Poi,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from custom_components.efteling.data import EftelingConfigEntry


MONTHS_PER_YEAR = 12


class EftelingCoordinator[DataT](DataUpdateCoordinator[DataT]):
    """Base coordinator with an injected Efteling API client."""

    config_entry: EftelingConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: EftelingApiClient,
        config_entry: EftelingConfigEntry,
        *,
        name: str,
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{name}",
            update_interval=update_interval,
        )
        self.client = client


class EftelingPoiUpdateCoordinator(EftelingCoordinator[dict[str, Poi]]):
    """Retrieve POIs indexed by primary and alternate ID."""

    async def _async_update_data(self) -> dict[str, Poi]:
        """Fetch and index all POIs."""
        try:
            poi_list = await self.client.async_get_poi_list()
        except EftelingApiClientError as exception:
            raise UpdateFailed(exception) from exception

        poi_map: dict[str, Poi] = {}
        for poi in poi_list:
            poi_map[poi["id"]] = poi
            alternate_id = poi.get("alternateid")
            if alternate_id:
                poi_map[alternate_id] = poi
        return poi_map


class EftelingWaitTimesUpdateCoordinator(
    EftelingCoordinator[dict[str, AttractionInfo]],
):
    """Retrieve live attraction and show information indexed by ID."""

    async def _async_update_data(self) -> dict[str, AttractionInfo]:
        """Fetch and index live attraction and show information."""
        try:
            wait_times = await self.client.async_get_wait_times()
        except EftelingApiClientError as exception:
            raise UpdateFailed(exception) from exception

        return {item["Id"]: item for item in wait_times if item.get("Id")}


class EftelingParkInfoUpdateCoordinator(
    EftelingCoordinator[ParkInfoResponse],
):
    """Retrieve opening hours, maintenance and events for the current month."""

    async def _async_update_data(self) -> ParkInfoResponse:
        """Fetch park information for the current Efteling-local month."""
        now = dt_util.now(PARK_TIME_ZONE)
        try:
            return await self.client.async_get_park_info(now.year, now.month)
        except EftelingApiClientError as exception:
            raise UpdateFailed(exception) from exception

    def start_monthly_refresh(self) -> Callable[[], None]:
        """Start a timer for the next month boundary and return its cleanup."""
        self._unsub_monthly_refresh = None
        self._schedule_monthly_refresh()
        return self._cancel_monthly_refresh

    @callback
    def _schedule_monthly_refresh(self) -> None:
        """Schedule an additional refresh at the next local month boundary."""
        self._cancel_monthly_refresh()
        now = dt_util.now(PARK_TIME_ZONE)
        if now.month == MONTHS_PER_YEAR:
            next_month = datetime(
                now.year + 1,
                1,
                1,
                tzinfo=PARK_TIME_ZONE,
            )
        else:
            next_month = datetime(
                now.year,
                now.month + 1,
                1,
                tzinfo=PARK_TIME_ZONE,
            )

        self._unsub_monthly_refresh = async_track_point_in_time(
            self.hass,
            self._handle_month_boundary,
            next_month,
        )

    @callback
    def _handle_month_boundary(self, _: datetime) -> None:
        """Refresh data when the calendar month changes."""
        self._unsub_monthly_refresh = None
        self.config_entry.async_create_task(self.hass, self.async_refresh())
        self._schedule_monthly_refresh()

    @callback
    def _cancel_monthly_refresh(self) -> None:
        """Cancel the scheduled month-boundary refresh."""
        if self._unsub_monthly_refresh is not None:
            self._unsub_monthly_refresh()
            self._unsub_monthly_refresh = None
