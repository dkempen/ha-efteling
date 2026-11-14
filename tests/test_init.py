"""Tests for Efteling integration setup and teardown."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, timedelta
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import SOURCE_RECONFIGURE, ConfigEntryState
from homeassistant.const import CONF_LANGUAGE
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util import dt as dt_util

from custom_components.efteling_park import PLATFORMS, async_unload_entry
from custom_components.efteling_park.api import (
    EftelingApiClient,
    EftelingApiClientCommunicationError,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant.common import MockConfigEntry


async def test_setup_and_unload(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Forward platforms, load entities, and unload their listeners cleanly."""
    assert loaded_entry.state is ConfigEntryState.LOADED
    assert hass.states.async_entity_ids("sensor")
    assert await hass.config_entries.async_unload(loaded_entry.entry_id)
    await hass.async_block_till_done()
    assert loaded_entry.state is ConfigEntryState.NOT_LOADED


async def test_changed_map_metadata_notifies_listeners(
    loaded_entry: MockConfigEntry,
) -> None:
    """Publish changed metadata to listeners registered during setup."""
    runtime_data = loaded_entry.runtime_data
    assert runtime_data.park_map is not None
    listener = MagicMock()
    runtime_data.map_metadata_listeners.append(listener)
    updated_metadata = replace(runtime_data.park_map, rotation_degrees=91)

    runtime_data.map_metadata_coordinator.async_set_updated_data(updated_metadata)

    assert runtime_data.park_map is updated_metadata
    listener.assert_called_once_with(updated_metadata)


async def test_unload_entry_returns_platform_unload_result(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Return the result from unloading all integration platforms."""
    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        new_callable=AsyncMock,
        return_value=False,
    ) as unload_platforms:
        assert await async_unload_entry(hass, config_entry) is False

    unload_platforms.assert_awaited_once_with(config_entry, PLATFORMS)


async def test_scheduled_callbacks_are_cancelled_on_unload(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    api_responses: None,
) -> None:
    """Cancel coordinator and entity timers when the integration unloads."""
    del api_responses
    names = (
        "map",
        "park_sensor",
        "park_event",
        "park_status",
        "annual_passes",
        "show",
        "coordinator",
    )
    removers = {name: MagicMock() for name in names}
    with (
        patch(
            "custom_components.efteling_park.image.park_map.async_track_point_in_time",
            return_value=removers["map"],
        ),
        patch(
            "custom_components.efteling_park.sensor.park.async_track_point_in_time",
            return_value=removers["park_sensor"],
        ),
        patch(
            "custom_components.efteling_park.binary_sensor.park_event.async_track_point_in_time",
            return_value=removers["park_event"],
        ),
        patch(
            "custom_components.efteling_park.binary_sensor.park_status.async_track_point_in_time",
            return_value=removers["park_status"],
        ),
        patch(
            "custom_components.efteling_park.binary_sensor.annual_passes.async_track_point_in_time",
            return_value=removers["annual_passes"],
        ),
        patch(
            "custom_components.efteling_park.sensor.show.async_track_point_in_time",
            return_value=removers["show"],
        ) as show_schedule,
        patch(
            "custom_components.efteling_park.coordinator.async_track_point_in_time",
            return_value=removers["coordinator"],
        ),
    ):
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        start = dt_util.now(UTC) + timedelta(hours=1)
        end = start + timedelta(minutes=15)
        config_entry.runtime_data.wait_times_coordinator.async_set_updated_data(
            {
                "aquanura": {
                    "Id": "aquanura",
                    "Name": "Aquanura",
                    "State": "open",
                    "ShowTimes": [
                        {
                            "StartDateTime": start.isoformat(),
                            "EndDateTime": end.isoformat(),
                            "Duration": 15,
                            "Edition": "Test",
                        }
                    ],
                    "PastShowTimes": [],
                }
            }
        )
        await hass.async_block_till_done()
        show_schedule.assert_called_once()
        assert await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()

    assert all(remover.called for remover in removers.values())


@pytest.mark.parametrize(
    "method_name",
    [
        "async_get_poi_list",
        "async_get_wait_times",
        "async_get_park_info",
        "async_get_annual_passes",
    ],
)
async def test_initial_coordinator_failure_retries_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    api_responses: None,
    method_name: str,
) -> None:
    """Let Home Assistant retry when any initial endpoint refresh fails."""
    del api_responses

    with patch.object(
        EftelingApiClient,
        method_name,
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
            "custom_components.efteling_park.EftelingApiClient",
            wraps=EftelingApiClient,
        ) as setup_client,
        patch(
            "custom_components.efteling_park.config_flow.EftelingApiClient",
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
    assert loaded_entry.data[CONF_LANGUAGE] == "nl"
    assert loaded_entry.options[CONF_LANGUAGE] == "en"
    assert loaded_entry.state is ConfigEntryState.LOADED
    assert validation_client.call_count == 1
    assert validation_client.call_args.kwargs["language"] == "en"
    assert setup_client.call_count == 1
    assert setup_client.call_args.kwargs["language"] == "en"
