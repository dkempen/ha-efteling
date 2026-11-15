"""Tests for the Efteling park map image."""

from __future__ import annotations

from datetime import datetime, timedelta
from importlib import import_module
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.image import Image, ImageEntity
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from collections.abc import Callable

    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
    from pytest_homeassistant.typing import ClientSessionGenerator

    from custom_components.efteling_park.image.park_map import MapSeason
else:
    try:
        async_fire_time_changed = import_module(
            "pytest_homeassistant.common"
        ).async_fire_time_changed
    except ModuleNotFoundError:
        async_fire_time_changed = import_module(
            "pytest_homeassistant_custom_component.common"
        ).async_fire_time_changed

from custom_components.efteling_park.const import PARK_TIME_ZONE
from custom_components.efteling_park.image.park_map import MAP_IMAGE_URLS
from custom_components.efteling_park.map import ParkMapMetadata

MAP_BOUNDS = {
    "min_latitude": 51.64599309,
    "max_latitude": 51.65379826,
    "min_longitude": 5.04264951,
    "max_longitude": 5.05522907,
}


def _park_info(events: list[dict[str, str]]) -> dict:
    """Return park information for the test date."""
    return {
        "OpeningHours": [
            {
                "Date": "2026-10-23",
                "OpeningHours": [],
            }
        ],
        "Maintenance": [],
        "Events": events,
    }


async def _async_get_image(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    entity_id: str,
) -> Image:
    """Fetch an image through Home Assistant's image endpoint."""
    await async_setup_component(hass, "http", {})
    state = hass.states.get(entity_id)
    assert state is not None

    client = await hass_client()
    response = await client.get(state.attributes["entity_picture"])

    assert response.status == 200
    return Image(response.headers["Content-Type"], await response.read())


@pytest.mark.parametrize(
    "season_case",
    [
        (
            [],
            "summer",
        ),
        (
            [
                {
                    "DateFrom": dt_util.now(PARK_TIME_ZONE).date().isoformat(),
                    "DateTo": dt_util.now(PARK_TIME_ZONE).date().isoformat(),
                    "Type": "winter",
                    "Name": "Winter Efteling",
                }
            ],
            "winter",
        ),
    ],
)
async def test_park_map_uses_current_season(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    loaded_entry: MockConfigEntry,
    season_case: tuple[list[dict[str, str]], MapSeason],
    entity_registry_entry: Callable[[MockConfigEntry, str], er.RegistryEntry],
) -> None:
    """Fetch the summer or winter map according to today's park events."""
    events, season = season_case
    load_image = AsyncMock(return_value=Image("image/jpeg", b"map image"))

    with patch.object(ImageEntity, "_async_load_image_from_url", load_image):
        await hass.async_block_till_done()

        map_entity_id = entity_registry_entry(loaded_entry, "park_map").entity_id

        loaded_entry.runtime_data.park_info_coordinator.async_set_updated_data(
            _park_info(events)
        )
        await hass.async_block_till_done()

        image = await _async_get_image(hass, hass_client, map_entity_id)

        assert image.content == b"map image"
        load_image.assert_awaited_once_with(MAP_IMAGE_URLS[season])

        state = hass.states.get(map_entity_id)

        assert state is not None

        expected_time = "12" if season == "summer" else "18"

        assert state.state == f"2026-11-06T22:22:{expected_time}+00:00"
        assert {name: state.attributes[name] for name in MAP_BOUNDS} == MAP_BOUNDS
        assert state.attributes["rotation_degrees"] == 90


async def test_park_map_reschedules_at_midnight(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    entity_registry_entry: Callable[[MockConfigEntry, str], er.RegistryEntry],
) -> None:
    """Refresh the image entity and schedule another update at midnight."""
    await hass.async_block_till_done()

    freezer.tick(timedelta(days=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    map_entity_id = entity_registry_entry(loaded_entry, "park_map").entity_id

    assert hass.states.get(map_entity_id) is not None


async def test_map_image_is_cached_until_the_season_changes(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    loaded_entry: MockConfigEntry,
    entity_registry_entry: Callable[[MockConfigEntry, str], er.RegistryEntry],
) -> None:
    """Reuse the map image within a season and reload it after a season change."""
    load_image = AsyncMock(return_value=Image("image/jpeg", b"map image"))
    today = dt_util.now(PARK_TIME_ZONE).date().isoformat()
    with patch.object(ImageEntity, "_async_load_image_from_url", load_image):
        entity_id = entity_registry_entry(loaded_entry, "park_map").entity_id
        runtime_data = loaded_entry.runtime_data
        runtime_data.park_info_coordinator.async_set_updated_data(
            {"OpeningHours": [], "Maintenance": [], "Events": []}
        )
        await hass.async_block_till_done()
        await _async_get_image(hass, hass_client, entity_id)
        await _async_get_image(hass, hass_client, entity_id)
        assert load_image.await_count == 1
        assert load_image.await_args_list[0].args[0] == MAP_IMAGE_URLS["summer"]

        runtime_data.park_info_coordinator.async_set_updated_data(
            {
                "OpeningHours": [],
                "Maintenance": [],
                "Events": [
                    {
                        "DateFrom": today,
                        "DateTo": today,
                        "Type": "winter",
                        "Name": "Winter Efteling",
                    }
                ],
            }
        )
        await hass.async_block_till_done()
        await _async_get_image(hass, hass_client, entity_id)

    assert load_image.await_count == 2
    assert load_image.await_args_list[1].args[0] == MAP_IMAGE_URLS["winter"]


async def test_map_image_cache_invalidates_when_manifest_timestamp_changes(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    loaded_entry: MockConfigEntry,
    entity_registry_entry: Callable[[MockConfigEntry, str], er.RegistryEntry],
) -> None:
    """Reload the selected image after its manifest timestamp changes."""
    load_image = AsyncMock(return_value=Image("image/jpeg", b"map image"))
    with patch.object(ImageEntity, "_async_load_image_from_url", load_image):
        entity_id = entity_registry_entry(loaded_entry, "park_map").entity_id
        metadata = loaded_entry.runtime_data.park_map
        assert metadata is not None
        await _async_get_image(hass, hass_client, entity_id)

        changed_manifest = dict(metadata.manifest)
        changed_manifest["summer"] += timedelta(minutes=1)
        updated = ParkMapMetadata(
            manifest=changed_manifest,
            bounds=metadata.bounds,
            rotation_degrees=metadata.rotation_degrees,
        )
        loaded_entry.runtime_data.map_metadata_coordinator.async_set_updated_data(
            updated
        )
        await hass.async_block_till_done()
        await _async_get_image(hass, hass_client, entity_id)

    assert load_image.await_count == 2


async def test_map_image_updates_bounds_without_reloading_unchanged_image(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    loaded_entry: MockConfigEntry,
    entity_registry_entry: Callable[[MockConfigEntry, str], er.RegistryEntry],
) -> None:
    """Refresh map attributes without invalidating an unchanged image version."""
    load_image = AsyncMock(return_value=Image("image/jpeg", b"map image"))
    with patch.object(ImageEntity, "_async_load_image_from_url", load_image):
        entity_id = entity_registry_entry(loaded_entry, "park_map").entity_id
        metadata = loaded_entry.runtime_data.park_map
        assert metadata is not None

        await _async_get_image(hass, hass_client, entity_id)

        updated_bounds = dict(metadata.bounds or MAP_BOUNDS)
        updated_bounds["min_latitude"] += 0.0001
        updated = ParkMapMetadata(
            manifest=metadata.manifest,
            bounds=updated_bounds,
            rotation_degrees=180,
        )
        loaded_entry.runtime_data.map_metadata_coordinator.async_set_updated_data(
            updated
        )
        await hass.async_block_till_done()
        await _async_get_image(hass, hass_client, entity_id)

    assert load_image.await_count == 1
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["min_latitude"] == updated_bounds["min_latitude"]
    assert state.attributes["rotation_degrees"] == 180


@pytest.mark.parametrize(
    "schedule_case",
    [
        (
            datetime(2026, 3, 28, 23, 30, tzinfo=PARK_TIME_ZONE),
            datetime(2026, 3, 29, 0, 0, tzinfo=PARK_TIME_ZONE),
        ),
        (
            datetime(2026, 10, 24, 23, 30, tzinfo=PARK_TIME_ZONE),
            datetime(2026, 10, 25, 0, 0, tzinfo=PARK_TIME_ZONE),
        ),
    ],
)
async def test_map_midnight_schedule_uses_local_calendar_midnight_across_dst(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    api_responses: None,
    freezer: FrozenDateTimeFactory,
    schedule_case: tuple[datetime, datetime],
) -> None:
    """Schedule map refreshes at park-local midnight around both DST changes."""
    del api_responses
    local_now, expected_midnight = schedule_case
    freezer.move_to(local_now)
    config_entry.add_to_hass(hass)
    unsubscribe = MagicMock()
    with patch(
        "custom_components.efteling_park.image.park_map.async_track_point_in_time",
        return_value=unsubscribe,
    ) as schedule_midnight:
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        schedule_midnight.assert_called_once()
        assert schedule_midnight.call_args.args[2] == expected_midnight

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
