"""
Custom integration to integrate Efteling with Home Assistant.

For more details about this integration, please refer to
https://github.com/dkempen/ha-efteling
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_loaded_integration

from custom_components.efteling.const import DOMAIN, LOGGER

from .api import EftelingApiClient
from .coordinator import (
    EftelingPoiUpdateCoordinator,
    EftelingWaitTimesUpdateCoordinator,
)
from .data import EftelingData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import EftelingConfigEntry

PLATFORMS: list[Platform] = [Platform.SENSOR]


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(
    hass: HomeAssistant,
    entry: EftelingConfigEntry,
) -> bool:
    """Set up this integration using UI."""
    poi_coordinator = EftelingPoiUpdateCoordinator(
        hass=hass,
        logger=LOGGER,
        name=f"{DOMAIN}_poi",
        update_interval=timedelta(days=1),
    )

    wait_times_coordinator = EftelingWaitTimesUpdateCoordinator(
        hass=hass,
        logger=LOGGER,
        name=f"{DOMAIN}_wait_times",
        update_interval=timedelta(minutes=5),
    )

    entry.runtime_data = EftelingData(
        client=EftelingApiClient(session=async_get_clientsession(hass)),
        integration=async_get_loaded_integration(hass, entry.domain),
        poi_coordinator=poi_coordinator,
        wait_times_coordinator=wait_times_coordinator,
    )

    await poi_coordinator.async_config_entry_first_refresh()
    await wait_times_coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: EftelingConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant,
    entry: EftelingConfigEntry,
) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
