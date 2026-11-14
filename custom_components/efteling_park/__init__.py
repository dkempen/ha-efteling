"""
Custom integration to integrate Efteling with Home Assistant.

For more details about this integration, please refer to
https://github.com/dkempen/ha-efteling
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.efteling_park.const import (
    CONF_LANGUAGE,
    DEFAULT_LANGUAGE,
)
from custom_components.efteling_park.coordinator import (
    EftelingAnnualPassesCoordinator,
    EftelingMapMetadataCoordinator,
    EftelingParkInfoCoordinator,
    EftelingPoiCoordinator,
    EftelingWaitTimesCoordinator,
)

from .api import EftelingApiClient
from .data import EftelingData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import EftelingConfigEntry

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.IMAGE,
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EftelingConfigEntry,
) -> bool:
    """Set up this integration using UI."""
    client = EftelingApiClient(
        session=async_get_clientsession(hass),
        language=entry.options.get(
            CONF_LANGUAGE,
            entry.data.get(CONF_LANGUAGE, DEFAULT_LANGUAGE),
        ),
    )

    poi_coordinator = EftelingPoiCoordinator(
        hass=hass,
        client=client,
        config_entry=entry,
        name="poi",
        update_interval=timedelta(days=1),
    )
    wait_times_coordinator = EftelingWaitTimesCoordinator(
        hass=hass,
        client=client,
        config_entry=entry,
        name="wait_times",
        update_interval=timedelta(minutes=5),
    )
    park_info_coordinator = EftelingParkInfoCoordinator(
        hass=hass,
        client=client,
        config_entry=entry,
        name="park_info",
        update_interval=timedelta(days=1),
    )
    annual_passes_coordinator = EftelingAnnualPassesCoordinator(
        hass=hass,
        client=client,
        config_entry=entry,
        name="annual_passes",
        update_interval=timedelta(days=1),
    )
    map_metadata_coordinator = EftelingMapMetadataCoordinator(hass, entry)
    await map_metadata_coordinator.async_refresh()

    entry.runtime_data = EftelingData(
        client=client,
        poi_coordinator=poi_coordinator,
        wait_times_coordinator=wait_times_coordinator,
        park_info_coordinator=park_info_coordinator,
        annual_passes_coordinator=annual_passes_coordinator,
        map_metadata_coordinator=map_metadata_coordinator,
        park_map=map_metadata_coordinator.data,
    )

    refresh_results = await asyncio.gather(
        poi_coordinator.async_config_entry_first_refresh(),
        wait_times_coordinator.async_config_entry_first_refresh(),
        park_info_coordinator.async_config_entry_first_refresh(),
        annual_passes_coordinator.async_config_entry_first_refresh(),
        return_exceptions=True,
    )

    for result in refresh_results:
        if isinstance(result, BaseException):
            raise result

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    entry.async_on_unload(park_info_coordinator.start_monthly_refresh())

    def update_map_metadata() -> None:
        """Publish changed map metadata to dependent entities."""
        metadata = map_metadata_coordinator.data
        if metadata is None or metadata == entry.runtime_data.park_map:
            return
        entry.runtime_data.park_map = metadata
        for update in tuple(entry.runtime_data.map_metadata_listeners):
            update(metadata)

    entry.async_on_unload(
        map_metadata_coordinator.async_add_listener(update_map_metadata)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: EftelingConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_update_options(
    hass: HomeAssistant,
    entry: EftelingConfigEntry,
) -> None:
    """Reload the integration when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
