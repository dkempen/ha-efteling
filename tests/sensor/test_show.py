"""Tests for Efteling show sensors."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
from homeassistant.util import dt as dt_util

from custom_components.efteling_park.sensor import show as show_module

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant, State
    from homeassistant.helpers.entity_registry import RegistryEntry
    from pytest_homeassistant.common import MockConfigEntry


async def test_show_has_stable_identity_and_empty_schedule_is_unknown(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    entity_registry_entry: Callable[[MockConfigEntry, str], RegistryEntry],
    entity_state: Callable[[str], State],
) -> None:
    """Expose POI metadata even when a show has no scheduled performances."""
    entity = entity_registry_entry(loaded_entry, "aquanura")

    loaded_entry.runtime_data.wait_times_coordinator.async_set_updated_data(
        {
            "aquanura": {
                "Id": "aquanura",
                "Name": "Aquanura",
                "State": "open",
                "ShowTimes": [],
                "PastShowTimes": [],
            }
        }
    )
    await hass.async_block_till_done()

    state = entity_state(entity.entity_id)

    # No showtime means the timestamp remains unknown.
    assert state.state == "unknown"

    # Schedule attributes remain available and have consistent types.
    assert state.attributes["id"] == "aquanura"
    assert state.attributes["status"] == "no_more_shows_today"
    assert state.attributes["current_show_end"] is None
    assert state.attributes["previous_showtimes"] == []
    assert state.attributes["upcoming_showtimes"] == []
    assert state.attributes["edition"] is None

    # POI metadata must still be exposed.
    assert state.attributes["empire"] == "Fantasierijk"
    assert state.attributes["description"].startswith("Sluit je dag in de Efteling af")
    assert (
        state.attributes["subtitle"]
        == "Laat je verwonderen door dit muzikale spektakel"
    )
    assert state.attributes["latitude"] == 51.648014
    assert state.attributes["longitude"] == 5.045388
    assert state.attributes["properties"] == [
        "attractionforfamiliy",
        "outdoorattraction",
        "easilyaccessiblewheelchairs",
        "assistancedogs",
    ]
    assert state.attributes["type"] == "Watershow"
    assert state.attributes["image"].startswith("https://www.efteling.com/")
    assert state.attributes["image_detail"].startswith("https://www.efteling.com/")
    assert state.attributes["sensor_type"] == "show_start_time"

    # Static POI duration is used when no live showtime duration exists.
    assert state.attributes["duration_minutes"] == 14


async def test_showtime_transitions_and_metadata_updates(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    entity_registry_entry: Callable[[MockConfigEntry, str], RegistryEntry],
    entity_state: Callable[[str], State],
) -> None:
    """Expose current, upcoming, and past showtimes with scheduled updates."""
    park_timezone = ZoneInfo("Europe/Amsterdam")
    now = datetime(2026, 10, 23, 12, 0, tzinfo=park_timezone)
    monkeypatch.setattr(
        "custom_components.efteling_park.sensor.show.dt_util.now",
        lambda _tz=None: now,
    )
    show = entity_registry_entry(loaded_entry, "aquanura")
    future_unsubscribe = AsyncMock()
    timer_unsubscribe = MagicMock()
    with patch(
        "custom_components.efteling_park.sensor.show.async_track_point_in_time",
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
                        {
                            "StartDateTime": "2026-10-23T16:00:00",
                            "EndDateTime": "2026-10-23T16:30:00",
                            "Duration": "unknown",
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
        state = entity_state(show.entity_id)
        assert state.attributes["status"] == "current"
        assert state.attributes["sensor_type"] == "show_start_time"
        assert state.attributes["duration_minutes"] == 60
        assert state.attributes["edition"] == "Matinee"
        assert len(state.attributes["previous_showtimes"]) == 1
        assert len(state.attributes["upcoming_showtimes"]) == 2
        assert track.call_count == 1

        now = datetime(2026, 10, 23, 12, 40, tzinfo=park_timezone)
        callback = track.call_args.args[1]
        callback(track.call_args.args[2])
        await hass.async_block_till_done()
        state = entity_state(show.entity_id)
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
    state = entity_state(show.entity_id)
    assert state.attributes["description"] == "Updated show details"
    future_unsubscribe.assert_not_called()


async def test_show_status_uses_park_date_and_next_timestamp_spans_dates(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    entity_registry_entry: Callable[[MockConfigEntry, str], RegistryEntry],
    entity_state: Callable[[str], State],
) -> None:
    """Classify today in the park timezone while retaining tomorrow's timestamp."""
    park_timezone = ZoneInfo("Europe/Amsterdam")
    now = datetime(2026, 10, 23, 23, 30, tzinfo=park_timezone)
    monkeypatch.setattr(
        "custom_components.efteling_park.sensor.show.dt_util.now",
        lambda _tz=None: now,
    )
    await hass.config.async_set_time_zone("America/New_York")
    show = entity_registry_entry(loaded_entry, "aquanura")
    wait_times = dict(loaded_entry.runtime_data.wait_times_coordinator.data)
    wait_times["aquanura"] = {
        "Id": "aquanura",
        "Name": "Aquanura",
        "State": "open",
        "ShowTimes": [
            {
                "StartDateTime": "2026-10-24T00:15:00",
                "EndDateTime": "2026-10-24T00:45:00",
            },
            {
                "StartDateTime": "2026-10-24T10:00:00",
                "EndDateTime": "2026-10-24T10:30:00",
            },
        ],
    }
    loaded_entry.runtime_data.wait_times_coordinator.async_set_updated_data(wait_times)
    await hass.async_block_till_done()

    state = entity_state(show.entity_id)
    assert state.attributes["status"] == "no_more_shows_today"
    assert len(state.attributes["upcoming_showtimes"]) == 2
    next_show = dt_util.parse_datetime(state.state)
    assert next_show is not None
    assert next_show.astimezone(park_timezone).date().isoformat() == "2026-10-24"

    wait_times["aquanura"]["ShowTimes"].append(
        {
            "StartDateTime": "2026-10-23T23:45:00",
            "EndDateTime": "2026-10-24T00:00:00",
        }
    )
    loaded_entry.runtime_data.wait_times_coordinator.async_set_updated_data(wait_times)
    await hass.async_block_till_done()
    state = entity_state(show.entity_id)
    assert state.attributes["status"] == "upcoming"
    next_show = dt_util.parse_datetime(state.state)
    assert next_show is not None
    assert next_show.astimezone(park_timezone).date().isoformat() == "2026-10-23"

    now = datetime(2026, 10, 24, 0, 0, tzinfo=park_timezone)
    loaded_entry.runtime_data.wait_times_coordinator.async_set_updated_data(wait_times)
    await hass.async_block_till_done()
    state = entity_state(show.entity_id)
    assert state.attributes["status"] == "upcoming"
    next_show = dt_util.parse_datetime(state.state)
    assert next_show is not None
    assert next_show.astimezone(park_timezone).date().isoformat() == "2026-10-24"


@pytest.fixture
def show_helpers(
    entity_registry_entry: Callable[[MockConfigEntry, str], RegistryEntry],
    entity_state: Callable[[str], State],
) -> tuple[
    Callable[[MockConfigEntry, str], RegistryEntry],
    Callable[[str], State],
]:
    """Provide entity registry and state helpers for show tests."""
    return entity_registry_entry, entity_state


@pytest.mark.parametrize(
    "dates",
    [
        ("2026-03-28", "2026-03-29"),
        ("2026-10-24", "2026-10-25"),
        ("2026-11-15", "2026-11-16"),
    ],
)
async def test_show_status_updates_at_park_midnight(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    show_helpers: tuple[
        Callable[[MockConfigEntry, str], RegistryEntry],
        Callable[[str], State],
    ],
    dates: tuple[str, str],
) -> None:
    """Update show status at local midnight, including across DST changes."""
    entity_registry_entry, entity_state = show_helpers
    today, tomorrow = dates
    """Update show status at local midnight, including across DST changes."""
    today, tomorrow = dates
    """Update show status at local midnight, including across DST changes."""
    park_timezone = ZoneInfo("Europe/Amsterdam")
    now = datetime.fromisoformat(f"{today}T23:30:00").replace(tzinfo=park_timezone)
    expected_midnight = datetime.fromisoformat(f"{tomorrow}T00:00:00").replace(
        tzinfo=park_timezone
    )

    monkeypatch.setattr(
        show_module.dt_util,
        "now",
        lambda _tz=None: now,
    )

    show = entity_registry_entry(loaded_entry, "aquanura")
    wait_times = dict(loaded_entry.runtime_data.wait_times_coordinator.data)
    wait_times["aquanura"] = {
        "Id": "aquanura",
        "Name": "Aquanura",
        "State": "open",
        "ShowTimes": [
            {
                "StartDateTime": f"{tomorrow}T00:15:00",
                "EndDateTime": f"{tomorrow}T00:45:00",
            }
        ],
    }

    with patch(
        "custom_components.efteling_park.sensor.show.async_track_point_in_time",
        return_value=MagicMock(),
    ) as schedule_update:
        loaded_entry.runtime_data.wait_times_coordinator.async_set_updated_data(
            wait_times
        )
        await hass.async_block_till_done()

        aquanura_calls = [
            call
            for call in schedule_update.call_args_list
            if getattr(call.args[1].__self__, "_show_id", None) == "aquanura"
        ]
        assert aquanura_calls

        midnight_call = next(
            call for call in aquanura_calls if call.args[2] == expected_midnight
        )

        assert entity_state(show.entity_id).attributes["status"] == (
            "no_more_shows_today"
        )

        now = expected_midnight
        midnight_call.args[1](expected_midnight)
        await hass.async_block_till_done()

        assert entity_state(show.entity_id).attributes["status"] == "upcoming"

        next_show_start = datetime.fromisoformat(f"{tomorrow}T00:15:00").replace(
            tzinfo=park_timezone
        )

        assert schedule_update.call_args.args[2] == next_show_start


async def test_show_without_end_or_duration_is_ignored(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    entity_registry_entry: Callable[[MockConfigEntry, str], RegistryEntry],
    entity_state: Callable[[str], State],
) -> None:
    """Ignore show records without a usable end time or duration."""
    now = datetime(2026, 10, 23, 12, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
    monkeypatch.setattr(
        "custom_components.efteling_park.sensor.show.dt_util.now",
        lambda _tz=None: now,
    )
    show = entity_registry_entry(loaded_entry, "aquanura")
    wait_times = dict(loaded_entry.runtime_data.wait_times_coordinator.data)
    wait_times["aquanura"] = {
        "Id": "aquanura",
        "Name": "Aquanura",
        "State": "open",
        "ShowTimes": [{"StartDateTime": "2026-10-23T14:00:00"}],
    }
    loaded_entry.runtime_data.wait_times_coordinator.async_set_updated_data(wait_times)
    await hass.async_block_till_done()

    state = entity_state(show.entity_id)
    assert state.state == "unknown"
    assert state.attributes["status"] == "no_more_shows_today"
