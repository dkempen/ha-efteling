"""Tests for Efteling park sensors."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.util import dt as dt_util

from custom_components.efteling_park.api import EftelingApiClientCommunicationError
from custom_components.efteling_park.const import PARK_TIME_ZONE
from custom_components.efteling_park.sensor.park import PARK_SENSOR_DESCRIPTIONS

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant, State
    from homeassistant.helpers.entity_registry import RegistryEntry
    from pytest_homeassistant.common import MockConfigEntry


async def test_park_metrics_require_today_and_live_sources(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    entity_registry_entry: Callable[[MockConfigEntry, str], RegistryEntry],
    entity_state: Callable[[str], State],
) -> None:
    """Mark date-dependent and live-derived metrics unavailable as needed."""
    forecast = entity_registry_entry(loaded_entry, "park_crowd_forecast")
    maintenance = entity_registry_entry(
        loaded_entry,
        "park_attractions_under_maintenance",
    )
    loaded_entry.runtime_data.park_info_coordinator.async_set_updated_data(
        {"OpeningHours": [], "Maintenance": [], "Events": []}
    )
    await hass.async_block_till_done()
    assert entity_state(forecast.entity_id).state == "unavailable"
    assert entity_state(maintenance.entity_id).state == "0"

    dates = [description.key for description in PARK_SENSOR_DESCRIPTIONS]
    assert "average_wait_time" in dates
    coordinator = loaded_entry.runtime_data.poi_coordinator
    client_method = loaded_entry.runtime_data.client.async_get_poi_list
    client_method.side_effect = EftelingApiClientCommunicationError("offline")
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    live = entity_registry_entry(loaded_entry, "park_average_wait_time")
    assert entity_state(live.entity_id).state == "unavailable"

    park_client_method = loaded_entry.runtime_data.client.async_get_park_info
    park_client_method.side_effect = EftelingApiClientCommunicationError("offline")
    await loaded_entry.runtime_data.park_info_coordinator.async_refresh()
    await hass.async_block_till_done()
    assert entity_state(forecast.entity_id).state == "unavailable"


async def test_live_park_metrics_do_not_depend_on_park_info(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    entity_registry_entry: Callable[[MockConfigEntry, str], RegistryEntry],
    entity_state: Callable[[str], State],
) -> None:
    """Keep live-derived metrics available when only park-info polling fails."""
    entity = entity_registry_entry(loaded_entry, "park_average_wait_time")
    client_method = loaded_entry.runtime_data.client.async_get_park_info
    client_method.side_effect = EftelingApiClientCommunicationError("offline")
    await loaded_entry.runtime_data.park_info_coordinator.async_refresh()
    await hass.async_block_till_done()

    assert entity_state(entity.entity_id).state != "unavailable"


async def test_crowd_level_threshold_boundaries(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    entity_registry_entry: Callable[[MockConfigEntry, str], RegistryEntry],
    entity_state: Callable[[str], State],
) -> None:
    """Classify the average wait using the integration's documented thresholds."""
    entity = entity_registry_entry(loaded_entry, "park_crowd_level")
    coordinator = loaded_entry.runtime_data.wait_times_coordinator
    expected = {
        0: "very_quiet",
        4: "very_quiet",
        5: "quiet",
        9: "quiet",
        10: "fairly_quiet",
        14: "fairly_quiet",
        15: "fairly_busy",
        19: "fairly_busy",
        20: "busy",
        24: "busy",
        25: "very_busy",
        29: "very_busy",
        30: "extremely_busy",
    }

    for waiting_time, crowd_level in expected.items():
        coordinator.async_set_updated_data(
            {
                attraction_id: {
                    **attraction,
                    "State": "open",
                    "WaitingTime": waiting_time,
                }
                for attraction_id, attraction in coordinator.data.items()
            }
        )
        await hass.async_block_till_done()
        assert entity_state(entity.entity_id).state == crowd_level


async def test_park_sensor_unknown_metric_is_unknown(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    api_responses: None,
    entity_registry_entry: Callable[[MockConfigEntry, str], RegistryEntry],
    entity_state: Callable[[str], State],
) -> None:
    """Keep the fallback value empty for an unsupported metric description."""
    del api_responses
    descriptions = (
        *PARK_SENSOR_DESCRIPTIONS,
        SensorEntityDescription(key="unsupported", translation_key="crowd_level"),
    )
    with patch(
        "custom_components.efteling_park.sensor.park.PARK_SENSOR_DESCRIPTIONS",
        descriptions,
    ):
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    entity = entity_registry_entry(config_entry, "park_unsupported")
    assert entity_state(entity.entity_id).state == "unknown"


async def test_park_forecast_attributes_for_current_schedule(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    entity_registry_entry: Callable[[MockConfigEntry, str], RegistryEntry],
    entity_state: Callable[[str], State],
) -> None:
    """Expose forecast and schedule attributes for today's park record."""
    today = dt_util.now(PARK_TIME_ZONE).date().isoformat()
    loaded_entry.runtime_data.park_info_coordinator.async_set_updated_data(
        {
            "OpeningHours": [
                {
                    "Date": today,
                    "OpeningHours": [{"Open": "10:00", "Close": "20:00"}],
                    "Crowded": 2,
                    "Crowdedness": 65,
                }
            ],
            "Maintenance": [],
            "Events": [],
        }
    )
    await hass.async_block_till_done()

    forecast = entity_registry_entry(loaded_entry, "park_crowd_forecast")
    state = entity_state(forecast.entity_id)
    assert state.state == "normal"
    assert state.attributes["daily_crowd_forecasts"][0]["forecast"] == "normal"

    occupancy = entity_registry_entry(loaded_entry, "park_occupancy_forecast")
    state = entity_state(occupancy.entity_id)
    assert state.state == "65"
    assert state.attributes["daily_occupancy_forecasts"][0]["occupancy"] == 65
