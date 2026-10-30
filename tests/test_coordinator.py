"""Tests for Efteling data coordinators."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.efteling.api import (
    EftelingApiClient,
    EftelingApiClientCommunicationError,
)
from custom_components.efteling.const import DOMAIN
from custom_components.efteling.coordinator import (
    EftelingCoordinator,
    EftelingParkInfoUpdateCoordinator,
    EftelingPoiUpdateCoordinator,
    EftelingWaitTimesUpdateCoordinator,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def _entry() -> MockConfigEntry:
    """Return a config entry for coordinator construction."""
    return MockConfigEntry(domain=DOMAIN, title="Efteling", data={}, unique_id=DOMAIN)


@pytest.mark.parametrize(
    ("coordinator_type", "method_name", "payload", "expected"),
    [
        (
            EftelingPoiUpdateCoordinator,
            "async_get_poi_list",
            [
                {
                    "id": "primary",
                    "name": "One",
                    "category": "attraction",
                    "alternateid": "alt",
                }
            ],
            {"primary", "alt"},
        ),
        (
            EftelingWaitTimesUpdateCoordinator,
            "async_get_wait_times",
            [
                {"Id": "one", "Name": "One", "State": "open"},
                {"Id": "", "Name": "Empty", "State": "open"},
            ],
            {"one"},
        ),
    ],
)
async def test_coordinator_indexes_api_records(
    hass: HomeAssistant,
    coordinator_type: type[EftelingCoordinator],
    method_name: str,
    payload: list[dict[str, object]],
    expected: set[str],
) -> None:
    """Index POIs and wait records by their primary identifiers."""
    entry = _entry()
    client = MagicMock(spec=EftelingApiClient)
    setattr(client, method_name, AsyncMock(return_value=payload))
    coordinator = coordinator_type(
        hass,
        client,
        entry,
        name="test",
        update_interval=timedelta(minutes=5),
    )
    await coordinator.async_refresh()
    assert set(coordinator.data) == expected
    if coordinator_type is EftelingPoiUpdateCoordinator:
        assert coordinator.data["primary"] is coordinator.data["alt"]


@pytest.mark.parametrize(
    ("coordinator_type", "method_name"),
    [
        (EftelingPoiUpdateCoordinator, "async_get_poi_list"),
        (EftelingWaitTimesUpdateCoordinator, "async_get_wait_times"),
        (EftelingParkInfoUpdateCoordinator, "async_get_park_info"),
    ],
)
async def test_coordinator_translates_api_errors_to_update_failed(
    hass: HomeAssistant,
    coordinator_type: type[EftelingCoordinator],
    method_name: str,
) -> None:
    """Convert client failures to Home Assistant coordinator failures."""
    entry = _entry()
    client = MagicMock(spec=EftelingApiClient)
    setattr(
        client,
        method_name,
        AsyncMock(side_effect=EftelingApiClientCommunicationError("offline")),
    )
    coordinator = coordinator_type(
        hass,
        client,
        entry,
        name="test",
        update_interval=timedelta(minutes=5),
    )
    await coordinator.async_refresh()
    assert coordinator.last_update_success is False


async def test_coordinator_refresh_recovers_after_communication_failure(
    hass: HomeAssistant,
) -> None:
    """Mark a failed refresh unavailable and restore success on recovery."""
    entry = _entry()
    client = MagicMock(spec=EftelingApiClient)
    client.async_get_poi_list = AsyncMock(
        side_effect=[EftelingApiClientCommunicationError("offline"), []]
    )
    coordinator = EftelingPoiUpdateCoordinator(
        hass,
        client,
        entry,
        name="poi",
        update_interval=timedelta(days=1),
    )
    await coordinator.async_refresh()
    assert coordinator.last_update_success is False
    await coordinator.async_refresh()
    assert coordinator.last_update_success is True
    assert coordinator.data == {}


async def test_park_month_refresh_uses_local_month_and_cleans_timer(
    hass: HomeAssistant,
) -> None:
    """Schedule the next local month boundary and return a timer cleanup."""
    entry = _entry()
    client = MagicMock(spec=EftelingApiClient)
    coordinator = EftelingParkInfoUpdateCoordinator(
        hass,
        client,
        entry,
        name="park_info",
        update_interval=timedelta(days=1),
    )
    unsubscribe = MagicMock()
    scheduled_at = datetime(2026, 10, 31, 12, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
    with (
        patch(
            "custom_components.efteling.coordinator.dt_util.now",
            return_value=scheduled_at,
        ),
        patch(
            "custom_components.efteling.coordinator.async_track_point_in_time",
            return_value=unsubscribe,
        ) as track,
    ):
        cleanup = coordinator.start_monthly_refresh()
        assert track.call_args.args[2] == datetime(
            2026, 11, 1, tzinfo=ZoneInfo("Europe/Amsterdam")
        )
        cleanup()
    unsubscribe.assert_called_once()


async def test_park_month_refresh_rolls_over_year_and_refreshes(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Refresh using January's year after a December month boundary."""
    coordinator = EftelingParkInfoUpdateCoordinator(
        hass,
        loaded_entry.runtime_data.client,
        loaded_entry,
        name="park_info_test",
        update_interval=timedelta(days=1),
    )
    unsubscribe = MagicMock()
    january = datetime(2027, 1, 1, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
    times = iter(
        [
            datetime(2026, 12, 31, 23, 59, tzinfo=ZoneInfo("Europe/Amsterdam")),
            january,
            january,
        ]
    )
    with (
        patch(
            "custom_components.efteling.coordinator.dt_util.now",
            side_effect=lambda _tz=None: next(times, january),
        ),
        patch(
            "custom_components.efteling.coordinator.async_track_point_in_time",
            return_value=unsubscribe,
        ) as track,
    ):
        cleanup = coordinator.start_monthly_refresh()
        assert track.call_args.args[2] == datetime(
            2027, 1, 1, tzinfo=ZoneInfo("Europe/Amsterdam")
        )
        callback = track.call_args.args[1]
        callback(track.call_args.args[2])
        await hass.async_block_till_done()
        cleanup()

    loaded_entry.runtime_data.client.async_get_park_info.assert_awaited_with(2027, 1)
    assert track.call_args.args[2] == datetime(
        2027, 2, 1, tzinfo=ZoneInfo("Europe/Amsterdam")
    )
