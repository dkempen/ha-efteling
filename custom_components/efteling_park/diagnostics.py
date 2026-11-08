"""Diagnostics for Efteling."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from custom_components.efteling_park.data import EftelingConfigEntry


TO_REDACT = frozenset(
    {
        "latlon",
        "latitude",
        "longitude",
        "Latitude",
        "Longitude",
    }
)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: EftelingConfigEntry,
) -> dict[str, Any]:
    """Return redacted coordinator data for a config entry."""
    del hass

    runtime_data = entry.runtime_data

    return {
        "config_entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "coordinators": {
            "poi": async_redact_data(runtime_data.poi_coordinator.data, TO_REDACT),
            "wait_times": async_redact_data(
                runtime_data.wait_times_coordinator.data,
                TO_REDACT,
            ),
            "park_info": async_redact_data(
                runtime_data.park_info_coordinator.data,
                TO_REDACT,
            ),
            "annual_passes": async_redact_data(
                runtime_data.annual_passes_coordinator.data,
                TO_REDACT,
            ),
        },
    }
