"""Tests for Efteling sensor platforms."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from custom_components.efteling.api import (
    EftelingApiClient,
    EftelingApiClientCommunicationError,
)
from custom_components.efteling.const import (
    ATTRACTIONS,
    DOMAIN,
    PARK,
    PARK_TIME_ZONE,
    SHOWS,
)
from custom_components.efteling.sensor.park import PARK_SENSOR_DESCRIPTIONS

if TYPE_CHECKING:
    import pytest
    from homeassistant.core import HomeAssistant, State
    from pytest_homeassistant_custom_component.common import MockConfigEntry


def _entity_for_unique_id(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    unique_id: str,
) -> er.RegistryEntry:
    """Find an entity registry entry owned by this config entry."""
    registry = er.async_get(hass)
    return next(
        entity
        for entity in registry.entities.values()
        if entity.config_entry_id == entry.entry_id and entity.unique_id == unique_id
    )


def _state(hass: HomeAssistant, entity_id: str) -> State:
    """Return the current state for a known entity ID."""
    state = hass.states.get(entity_id)
    if state is None:
        raise AssertionError
    return state


async def test_sensor_setup_preserves_entity_and_device_identity(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Create attraction/show entities with their existing registry identities."""
    attraction = _entity_for_unique_id(hass, loaded_entry, "python")
    show = _entity_for_unique_id(hass, loaded_entry, "aquanura")
    park = _entity_for_unique_id(hass, loaded_entry, "park_crowd_forecast")

    assert attraction.entity_id.startswith("sensor.")
    assert show.entity_id.startswith("sensor.")
    assert park.entity_id == "sensor.efteling_park_crowd_forecast"
    assert (
        len(
            [
                entity
                for entity in er.async_get(hass).entities.values()
                if entity.config_entry_id == loaded_entry.entry_id
                and entity.unique_id in {"python", "aquanura"}
            ]
        )
        == 2
    )

    devices = dr.async_entries_for_config_entry(
        dr.async_get(hass),
        loaded_entry.entry_id,
    )
    identifiers = {
        identifier for device in devices for identifier in device.identifiers
    }
    assert (DOMAIN, ATTRACTIONS) in identifiers
    assert (DOMAIN, SHOWS) in identifiers
    assert (DOMAIN, PARK) in identifiers


async def test_attraction_state_metadata_and_wait_failure_recovery(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Expose live wait and metadata, then become unavailable and recover."""
    entity = _entity_for_unique_id(hass, loaded_entry, "python")
    state = hass.states.get(entity.entity_id)
    assert state is not None
    assert state.state == "5"
    assert state.attributes["description"].startswith("Zet je wereld")
    assert state.attributes["latitude"] == 51.647575

    updated_poi = {
        "id": "python",
        "name": "Python",
        "category": "attraction",
        "detail_text": "Updated <b>description</b>",
        "latlon": "51.66,5.06",
    }
    loaded_entry.runtime_data.poi_coordinator.async_set_updated_data(
        {"python": updated_poi}
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity.entity_id)
    assert state is not None
    assert state.attributes["description"] == "Updated description"
    assert state.attributes["latitude"] == 51.66

    coordinator = loaded_entry.runtime_data.wait_times_coordinator
    client_method = loaded_entry.runtime_data.client.async_get_wait_times
    client_method.side_effect = EftelingApiClientCommunicationError("offline")
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert _state(hass, entity.entity_id).state == "unavailable"

    client_method.side_effect = None
    client_method.return_value = [
        {"Id": "python", "Name": "Python", "State": "open", "WaitingTime": 0},
        {"Id": "aquanura", "Name": "Aquanura", "State": "open", "ShowTimes": []},
    ]
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert _state(hass, entity.entity_id).state == "0"


async def test_attraction_closed_state_is_unknown_not_unavailable(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Keep a successfully fetched closed attraction available with no value."""
    entity = _entity_for_unique_id(hass, loaded_entry, "python")
    loaded_entry.runtime_data.wait_times_coordinator.async_set_updated_data(
        {
            "python": {
                "Id": "python",
                "Name": "Python",
                "State": "closed",
                "WaitingTime": None,
            }
        }
    )
    await hass.async_block_till_done()
    assert _state(hass, entity.entity_id).state == "unknown"


async def test_park_metrics_require_today_and_live_sources(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Mark date-dependent and live-derived metrics unavailable as needed."""
    forecast = _entity_for_unique_id(hass, loaded_entry, "park_crowd_forecast")
    maintenance = _entity_for_unique_id(
        hass,
        loaded_entry,
        "park_attractions_under_maintenance",
    )
    loaded_entry.runtime_data.park_info_coordinator.async_set_updated_data(
        {"OpeningHours": [], "Maintenance": [], "Events": []}
    )
    await hass.async_block_till_done()
    assert _state(hass, forecast.entity_id).state == "unavailable"
    assert _state(hass, maintenance.entity_id).state == "0"

    dates = [description.key for description in PARK_SENSOR_DESCRIPTIONS]
    assert "average_wait_time" in dates
    coordinator = loaded_entry.runtime_data.poi_coordinator
    client_method = loaded_entry.runtime_data.client.async_get_poi_list
    client_method.side_effect = EftelingApiClientCommunicationError("offline")
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    live = _entity_for_unique_id(hass, loaded_entry, "park_average_wait_time")
    assert _state(hass, live.entity_id).state == "unavailable"

    park_client_method = loaded_entry.runtime_data.client.async_get_park_info
    park_client_method.side_effect = EftelingApiClientCommunicationError("offline")
    await loaded_entry.runtime_data.park_info_coordinator.async_refresh()
    await hass.async_block_till_done()
    assert _state(hass, forecast.entity_id).state == "unavailable"


async def test_park_sensor_unknown_metric_is_unknown(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    api_responses: None,
) -> None:
    """Keep the fallback value empty for an unsupported metric description."""
    del api_responses
    descriptions = (
        *PARK_SENSOR_DESCRIPTIONS,
        SensorEntityDescription(key="unsupported", translation_key="crowd_level"),
    )
    with patch(
        "custom_components.efteling.sensor.park.PARK_SENSOR_DESCRIPTIONS",
        descriptions,
    ):
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    entity = _entity_for_unique_id(hass, config_entry, "park_unsupported")
    assert _state(hass, entity.entity_id).state == "unknown"


async def test_park_forecast_attributes_for_current_schedule(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
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

    forecast = _entity_for_unique_id(hass, loaded_entry, "park_crowd_forecast")
    state = hass.states.get(forecast.entity_id)
    assert state is not None
    assert state.state == "normal"
    assert state.attributes["daily_crowd_forecasts"][0]["forecast"] == "normal"

    occupancy = _entity_for_unique_id(hass, loaded_entry, "park_occupancy_forecast")
    state = hass.states.get(occupancy.entity_id)
    assert state is not None
    assert state.state == "65"
    assert state.attributes["daily_occupancy_forecasts"][0]["occupancy"] == 65


async def test_show_has_stable_identity_and_empty_schedule_is_unknown(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Create the show sensor by its existing unique ID with no fake time."""
    entity = _entity_for_unique_id(hass, loaded_entry, "aquanura")
    loaded_entry.runtime_data.wait_times_coordinator.async_set_updated_data(
        {
            "aquanura": {
                "Id": "aquanura",
                "Name": "Aquanura",
                "State": "open",
                "ShowTimes": [],
            }
        }
    )
    await hass.async_block_till_done()
    assert _state(hass, entity.entity_id).state == "unknown"


async def test_showtime_transitions_and_metadata_updates(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Expose current, upcoming, and past showtimes with scheduled updates."""
    park_timezone = ZoneInfo("Europe/Amsterdam")
    now = datetime(2026, 10, 23, 12, 0, tzinfo=park_timezone)
    monkeypatch.setattr(
        "custom_components.efteling.sensor.show.dt_util.now",
        lambda _tz=None: now,
    )
    show = _entity_for_unique_id(hass, loaded_entry, "aquanura")
    future_unsubscribe = AsyncMock()
    timer_unsubscribe = MagicMock()
    with patch(
        "custom_components.efteling.sensor.show.async_track_point_in_time",
        return_value=timer_unsubscribe,
    ) as track:
        loaded_entry.runtime_data.wait_times_coordinator.async_set_updated_data(
            {
                "aquanura": {
                    "Id": "aquanura",
                    "Name": "Aquanura",
                    "State": "open",
                    "ShowTimes": [
                        {"StartDateTime": "invalid", "Duration": 10},
                        {
                            "StartDateTime": "2026-10-23T11:30:00",
                            "Duration": 60,
                            "Edition": "Matinee",
                        },
                        {
                            "StartDateTime": "2026-10-23T14:00:00",
                            "EndDateTime": "2026-10-23T14:30:00",
                        },
                        {
                            "StartDateTime": "2026-10-23T15:00:00",
                            "EndDateTime": "2026-10-23T14:00:00",
                            "Duration": 0,
                        },
                    ],
                    "PastShowTimes": [
                        {
                            "StartDateTime": "2026-10-23T09:00:00",
                            "EndDateTime": "2026-10-23T10:00:00",
                        }
                    ],
                }
            }
        )
        await hass.async_block_till_done()
        state = hass.states.get(show.entity_id)
        assert state is not None
        assert state.attributes["status"] == "current"
        assert state.attributes["duration_minutes"] == 60
        assert state.attributes["edition"] == "Matinee"
        assert len(state.attributes["previous_showtimes"]) == 1
        assert len(state.attributes["upcoming_showtimes"]) == 1
        assert track.call_count == 1

        now = datetime(2026, 10, 23, 12, 40, tzinfo=park_timezone)
        callback = track.call_args.args[1]
        callback(track.call_args.args[2])
        await hass.async_block_till_done()
        state = hass.states.get(show.entity_id)
        assert state is not None
        assert state.attributes["status"] == "upcoming"
        assert track.call_count == 2

    loaded_entry.runtime_data.poi_coordinator.async_set_updated_data(
        {
            "aquanura": {
                "id": "aquanura",
                "name": "Aquanura",
                "category": "show",
                "detail_text": "Updated show details",
            }
        }
    )
    await hass.async_block_till_done()
    state = hass.states.get(show.entity_id)
    assert state is not None
    assert state.attributes["description"] == "Updated show details"
    future_unsubscribe.assert_not_called()


async def test_dynamic_sensor_creation_uses_names_and_ignores_unknown_pois(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    api_responses: None,
) -> None:
    """Create only supported entities and preserve custom naming conventions."""
    del api_responses
    poi_records = [
        {
            "id": "stoomtreinm",
            "name": "Train fallback",
            "category": "attraction",
            "wis_info": {"Name": "Official train"},
        },
        {
            "id": "stoomtreinr",
            "name": "Railway fallback",
            "category": "attraction",
            "wis_info": {},
        },
        {
            "id": "alternate",
            "name": "Ride",
            "category": "attraction",
            "alternateid": "alternate",
            "alternatelabel": "Single Rider",
        },
        {
            "id": "alternate-mismatch",
            "name": "Mismatch Ride",
            "category": "attraction",
            "alternateid": "different-id",
            "alternatelabel": "Single Rider",
        },
        {"id": "unknown", "name": "Unknown", "category": "restaurant"},
    ]
    wait_records = [
        {"Id": "stoomtreinm", "Name": "Train", "State": "open", "WaitingTime": 5},
        {"Id": "stoomtreinr", "Name": "Railway", "State": "open", "WaitingTime": 5},
        {"Id": "alternate", "Name": "Ride", "State": "open", "WaitingTime": 10},
        {
            "Id": "alternate-mismatch",
            "Name": "Mismatch Ride",
            "State": "open",
            "WaitingTime": 10,
        },
        {"Id": "unknown", "Name": "Unknown", "State": "open", "WaitingTime": 1},
        {"Id": "missing-poi", "Name": "Missing", "State": "open", "WaitingTime": 1},
    ]
    with (
        patch.object(
            EftelingApiClient,
            "async_get_poi_list",
            new_callable=AsyncMock,
            return_value=poi_records,
        ),
        patch.object(
            EftelingApiClient,
            "async_get_wait_times",
            new_callable=AsyncMock,
            return_value=wait_records,
        ),
        patch.object(
            EftelingApiClient,
            "async_get_park_info",
            new_callable=AsyncMock,
            return_value={"OpeningHours": [], "Maintenance": [], "Events": []},
        ),
    ):
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    train = _entity_for_unique_id(hass, config_entry, "stoomtreinm")
    railway = _entity_for_unique_id(hass, config_entry, "stoomtreinr")
    alternate = _entity_for_unique_id(hass, config_entry, "alternate")
    alternate_mismatch = _entity_for_unique_id(
        hass,
        config_entry,
        "alternate-mismatch",
    )
    assert train.original_name == "Official train"
    assert railway.original_name == "Railway fallback"
    assert alternate.original_name == "Ride Single Rider"
    assert alternate_mismatch.original_name == "Mismatch Ride"
    entity_ids = {
        entity.unique_id
        for entity in er.async_get(hass).entities.values()
        if entity.config_entry_id == config_entry.entry_id
    }
    assert "unknown" not in entity_ids
    assert "missing-poi" not in entity_ids


async def test_sensor_setup_without_supported_dynamic_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Set up Park sensors when the API has no dynamic entities to add."""
    with (
        patch.object(
            EftelingApiClient,
            "async_get_poi_list",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch.object(
            EftelingApiClient,
            "async_get_wait_times",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch.object(
            EftelingApiClient,
            "async_get_park_info",
            new_callable=AsyncMock,
            return_value={"OpeningHours": [], "Maintenance": [], "Events": []},
        ),
    ):
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    entity_ids = {
        entity.unique_id
        for entity in er.async_get(hass).entities.values()
        if entity.config_entry_id == config_entry.entry_id and entity.domain == "sensor"
    }
    assert entity_ids == {
        f"park_{description.key}" for description in PARK_SENSOR_DESCRIPTIONS
    }
