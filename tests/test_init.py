"""Tests for Efteling integration setup and teardown."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import SOURCE_RECONFIGURE, ConfigEntryState
from homeassistant.const import CONF_LANGUAGE
from homeassistant.data_entry_flow import FlowResultType

from custom_components.efteling.api import (
    EftelingApiClient,
    EftelingApiClientCommunicationError,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry


async def test_setup_and_unload(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Forward platforms, load entities, and unload their listeners cleanly."""
    assert loaded_entry.state is ConfigEntryState.LOADED
    assert hass.states.async_entity_ids("sensor")
    assert await hass.config_entries.async_unload(loaded_entry.entry_id)
    await hass.async_block_till_done()
    assert loaded_entry.state is ConfigEntryState.NOT_LOADED


async def test_initial_coordinator_failure_retries_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Let Home Assistant retry when an initial endpoint refresh fails."""
    with patch.object(
        EftelingApiClient,
        "async_get_poi_list",
        new_callable=AsyncMock,
        side_effect=EftelingApiClientCommunicationError("offline"),
    ):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_reconfigure_reloads_loaded_entry_with_new_language(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Recreate the API client with the language selected during reconfiguration."""
    with (
        patch(
            "custom_components.efteling.EftelingApiClient",
            wraps=EftelingApiClient,
        ) as setup_client,
        patch(
            "custom_components.efteling.config_flow.EftelingApiClient",
            wraps=EftelingApiClient,
        ) as validation_client,
    ):
        result = await hass.config_entries.flow.async_init(
            loaded_entry.domain,
            context={
                "source": SOURCE_RECONFIGURE,
                "entry_id": loaded_entry.entry_id,
            },
        )
        assert result.get("type") is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_LANGUAGE: "en"},
        )
        await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "reconfigure_successful"
    assert loaded_entry.data[CONF_LANGUAGE] == "en"
    assert loaded_entry.state is ConfigEntryState.LOADED
    assert validation_client.call_count == 1
    assert validation_client.call_args.kwargs["language"] == "en"
    assert setup_client.call_count == 1
    assert setup_client.call_args.kwargs["language"] == "en"
