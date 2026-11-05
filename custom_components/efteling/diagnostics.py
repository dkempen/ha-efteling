"""Diagnostics for Efteling."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from custom_components.efteling.data import EftelingConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: EftelingConfigEntry,
) -> dict[str, Any]:
    """Return coordinator data for a config entry."""
    del hass
    runtime_data = entry.runtime_data

    return {
        "config_entry": {"data": dict(entry.data)},
        "coordinators": {
            "poi": runtime_data.poi_coordinator.data,
            "wait_times": runtime_data.wait_times_coordinator.data,
            "park_info": runtime_data.park_info_coordinator.data,
            "annual_passes": runtime_data.annual_passes_coordinator.data,
        },
    }
