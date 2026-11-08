"""Tests for Efteling diagnostics."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.setup import async_setup_component

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
    }

    poi = diagnostics["data"]["coordinators"]["poi"]["python"]

    assert poi["name"] == "Python"
    assert poi["latlon"] == "**REDACTED**"
    assert poi["metadata"][0]["latitude"] == "**REDACTED**"
    assert poi["metadata"][0]["longitude"] == "**REDACTED**"
