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
    client = await hass_client()
    response = await client.get(
        f"/api/diagnostics/config_entry/{loaded_entry.entry_id}"
    )

    assert response.status == 200
    diagnostics = await response.json()

    assert diagnostics["data"]["config_entry"]["data"] == dict(loaded_entry.data)
    assert set(diagnostics["data"]["coordinators"]) == {
        "poi",
        "wait_times",
        "park_info",
        "annual_passes",
    }
