"""Tests for Efteling diagnostics."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.setup import async_setup_component

from custom_components.efteling_park.diagnostics import (
    async_get_config_entry_diagnostics,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant.common import MockConfigEntry
    from pytest_homeassistant.typing import ClientSessionGenerator


async def test_diagnostics_include_config_and_coordinator_data(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    loaded_entry: MockConfigEntry,
) -> None:
    """Serve coordinator snapshots and config-entry data."""
    await async_setup_component(hass, "http", {})
    await async_setup_component(hass, "diagnostics", {})

    loaded_entry.runtime_data.poi_coordinator.async_set_updated_data(
        {
            "python": {
                "id": "python",
                "name": "Python",
                "category": "attraction",
                "latlon": "51.647575, 5.043718",
                "metadata": [
                    {
                        "latitude": 51.647575,
                        "longitude": 5.043718,
                    }
                ],
            }
        }
    )
    await hass.async_block_till_done()

    client = await hass_client()
    response = await client.get(
        f"/api/diagnostics/config_entry/{loaded_entry.entry_id}"
    )

    assert response.status == 200
    diagnostics = await response.json()

    assert diagnostics["data"]["config_entry"]["data"] == dict(loaded_entry.data)
    assert diagnostics["data"]["config_entry"]["options"] == dict(loaded_entry.options)

    assert set(diagnostics["data"]["coordinators"]) == {
        "poi",
        "wait_times",
        "park_info",
        "annual_passes",
        "map",
    }

    poi = diagnostics["data"]["coordinators"]["poi"]["python"]

    assert poi["name"] == "Python"
    assert poi["latlon"] == "**REDACTED**"
    assert poi["metadata"][0]["latitude"] == "**REDACTED**"
    assert poi["metadata"][0]["longitude"] == "**REDACTED**"

    map_metadata = loaded_entry.runtime_data.park_map
    assert map_metadata is not None

    map_diagnostics = diagnostics["data"]["coordinators"]["map"]
    assert map_diagnostics == {
        "manifest": {
            "summer": "2026-11-06T22:22:12+00:00",
            "winter": "2026-11-06T22:22:18+00:00",
        },
        "bounds": {
            "min_latitude": "**REDACTED**",
            "max_latitude": "**REDACTED**",
            "min_longitude": "**REDACTED**",
            "max_longitude": "**REDACTED**",
        },
        "rotation_degrees": 90,
    }


async def test_diagnostics_redact_coordinates_recursively(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Redact coordinate fields at the root and in nested records."""
    loaded_entry.runtime_data.poi_coordinator.async_set_updated_data(
        {
            "python": {
                "id": "python",
                "name": "Python",
                "category": "attraction",
                "latlon": "51.647575,5.053534",
                "latitude": 51.647575,
                "longitude": 5.053534,
                "min_latitude": 51.64599309,
                "max_latitude": 51.65379826,
                "min_longitude": 5.04264951,
                "max_longitude": 5.05522907,
                "location": {"Latitude": 51.647575, "Longitude": 5.053534},
                "history": [{"latitude": 51.647575, "longitude": 5.053534}],
                "safe_field": "retained",
            }
        }
    )
    diagnostics = await async_get_config_entry_diagnostics(hass, loaded_entry)
    poi = diagnostics["coordinators"]["poi"]["python"]
    assert poi["latlon"] == "**REDACTED**"
    assert poi["latitude"] == "**REDACTED**"
    assert poi["longitude"] == "**REDACTED**"
    assert poi["min_latitude"] == "**REDACTED**"
    assert poi["max_latitude"] == "**REDACTED**"
    assert poi["min_longitude"] == "**REDACTED**"
    assert poi["max_longitude"] == "**REDACTED**"
    assert poi["location"]["Latitude"] == "**REDACTED**"
    assert poi["location"]["Longitude"] == "**REDACTED**"
    assert poi["history"][0]["latitude"] == "**REDACTED**"
    assert poi["history"][0]["longitude"] == "**REDACTED**"
    assert poi["safe_field"] == "retained"


async def test_diagnostics_report_missing_map_metadata(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Report map metadata as unavailable when no valid manifest is cached."""
    loaded_entry.runtime_data.map_metadata_coordinator.data = None

    diagnostics = await async_get_config_entry_diagnostics(hass, loaded_entry)
    assert diagnostics["coordinators"]["map"] is None
