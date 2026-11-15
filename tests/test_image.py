"""Tests for the Efteling image platform."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from importlib import import_module
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.image import Image, ImageEntity
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
    from pytest_homeassistant.typing import ClientSessionGenerator

    from custom_components.efteling_park.image.park_map import (
        MapSeason,
    )
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
from custom_components.efteling_park.image import async_setup_entry
from custom_components.efteling_park.image.park_map import MAP_IMAGE_URLS
from custom_components.efteling_park.map import ParkMapMetadata, _parse_map_bounds

MAP_BOUNDS = {
    "min_latitude": 51.64599309,
    "max_latitude": 51.65379826,
    "min_longitude": 5.04264951,
    "max_longitude": 5.05522907,
}


def _entity_id_for_unique_id(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    unique_id: str,
) -> str:
    """Find an image entity registry entry owned by this config entry."""
    registry = er.async_get(hass)
    return next(
        entity.entity_id
        for entity in registry.entities.values()
        if entity.config_entry_id == entry.entry_id and entity.unique_id == unique_id
    )


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


async def test_image_setup_entry_parses_manifest(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Create the map image entity from runtime map metadata."""
    add_entities = MagicMock()
    await async_setup_entry(hass, loaded_entry, add_entities)

    add_entities.assert_called_once()
    assert len(add_entities.call_args.args[0]) == 1


async def test_image_setup_entry_waits_for_missing_map_metadata(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Register a listener and create the map image when metadata becomes available."""
    runtime_data = loaded_entry.runtime_data
    metadata = runtime_data.park_map
    assert metadata is not None

    runtime_data.map_metadata_coordinator.data = None
    listeners_before = tuple(runtime_data.map_metadata_listeners)
    add_entities = MagicMock()

    await async_setup_entry(hass, loaded_entry, add_entities)

    add_entities.assert_not_called()
    assert len(runtime_data.map_metadata_listeners) == len(listeners_before) + 1

    listener = next(
        item
        for item in runtime_data.map_metadata_listeners
        if item not in listeners_before
    )

    listener(None)
    add_entities.assert_not_called()

    runtime_data.map_metadata_coordinator.async_set_updated_data(metadata)
    await hass.async_block_till_done()

    add_entities.assert_called_once()
    assert len(add_entities.call_args.args[0]) == 1
    assert listener not in runtime_data.map_metadata_listeners


def test_parse_map_bounds_accepts_missing_bounds() -> None:
    """Return no bounds when the manifest omits them."""
    assert _parse_map_bounds(None) is None


def test_parse_map_bounds_accepts_valid_bounds() -> None:
    """Parse valid map bounds into floating-point coordinates."""
    assert _parse_map_bounds(MAP_BOUNDS) == MAP_BOUNDS


def test_parse_map_bounds_rejects_non_object() -> None:
    """Reject bounds that are not represented by an object."""
    with pytest.raises(TypeError, match="geographic bounds must be an object"):
        _parse_map_bounds([])


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("min_latitude", 51.7),
        ("min_longitude", 5.06),
        ("max_latitude", 51.6),
        ("max_longitude", 5.04),
    ],
)
def test_parse_map_bounds_rejects_inverted_ranges(name: str, value: float) -> None:
    """Reject minimum bounds that exceed their corresponding maximum."""
    raw_bounds: dict[str, object] = dict(MAP_BOUNDS)
    raw_bounds[name] = value
    expected = "latitude" if "latitude" in name else "longitude"

    with pytest.raises(ValueError, match=f"Minimum map {expected}"):
        _parse_map_bounds(raw_bounds)


@pytest.mark.parametrize(
    ("events", "season"),
    [
        ([], "summer"),
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
    events: list[dict[str, str]],
    season: MapSeason,
) -> None:
    """Fetch the summer or winter map according to today's park events."""
    load_image = AsyncMock(return_value=Image("image/jpeg", b"map image"))

    with patch.object(ImageEntity, "_async_load_image_from_url", load_image):
        await hass.async_block_till_done()

        map_entity_id = _entity_id_for_unique_id(hass, loaded_entry, "park_map")

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
) -> None:
    """Refresh the image entity and schedule another update at midnight."""
    await hass.async_block_till_done()

    freezer.tick(timedelta(days=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    map_entity_id = _entity_id_for_unique_id(hass, loaded_entry, "park_map")

    assert hass.states.get(map_entity_id) is not None


async def test_map_image_is_cached_until_the_season_changes(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    loaded_entry: MockConfigEntry,
) -> None:
    """Reuse the map image within a season and reload it after a season change."""
    load_image = AsyncMock(return_value=Image("image/jpeg", b"map image"))
    today = dt_util.now(PARK_TIME_ZONE).date().isoformat()
    with patch.object(ImageEntity, "_async_load_image_from_url", load_image):
        entity_id = _entity_id_for_unique_id(hass, loaded_entry, "park_map")
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
) -> None:
    """Reload the selected image after its manifest timestamp changes."""
    load_image = AsyncMock(return_value=Image("image/jpeg", b"map image"))
    with patch.object(ImageEntity, "_async_load_image_from_url", load_image):
        entity_id = _entity_id_for_unique_id(hass, loaded_entry, "park_map")
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
) -> None:
    """Refresh map attributes without invalidating an unchanged image version."""
    load_image = AsyncMock(return_value=Image("image/jpeg", b"map image"))
    with patch.object(ImageEntity, "_async_load_image_from_url", load_image):
        entity_id = _entity_id_for_unique_id(hass, loaded_entry, "park_map")
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


@pytest.mark.parametrize(
    ("name", "value"),
    [
        pytest.param("min_latitude", True, id="min-latitude-boolean"),
        pytest.param("max_latitude", False, id="max-latitude-boolean"),
        pytest.param("min_longitude", True, id="min-longitude-boolean"),
        pytest.param("max_longitude", False, id="max-longitude-boolean"),
        pytest.param("min_latitude", "51.5", id="latitude-string"),
        pytest.param("max_longitude", "5.5", id="longitude-string"),
        pytest.param("min_latitude", None, id="null-coordinate"),
        pytest.param("max_latitude", [], id="list-coordinate"),
        pytest.param("min_longitude", {}, id="dict-coordinate"),
    ],
)
def test_parse_map_bounds_rejects_invalid_coordinate_types(
    name: str,
    value: object,
) -> None:
    """Reject coordinates that are not numeric values or are booleans."""
    raw_bounds: dict[str, object] = dict(MAP_BOUNDS)
    raw_bounds[name] = value

    with pytest.raises(
        TypeError,
        match=re.escape(f"Invalid geographic map bound '{name}'."),
    ):
        _parse_map_bounds(raw_bounds)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        pytest.param("min_latitude", -90.1, id="min-latitude-below-range"),
        pytest.param("min_latitude", 90.1, id="min-latitude-above-range"),
        pytest.param("max_latitude", -90.1, id="max-latitude-below-range"),
        pytest.param("max_latitude", 90.1, id="max-latitude-above-range"),
        pytest.param("min_longitude", -180.1, id="min-longitude-below-range"),
        pytest.param("min_longitude", 180.1, id="min-longitude-above-range"),
        pytest.param("max_longitude", -180.1, id="max-longitude-below-range"),
        pytest.param("max_longitude", 180.1, id="max-longitude-above-range"),
        pytest.param("min_latitude", float("nan"), id="latitude-nan"),
        pytest.param("max_longitude", float("nan"), id="longitude-nan"),
    ],
)
def test_parse_map_bounds_rejects_out_of_range_coordinates(
    name: str,
    value: float,
) -> None:
    """Reject coordinates outside their valid geographic ranges."""
    raw_bounds: dict[str, object] = dict(MAP_BOUNDS)
    raw_bounds[name] = value

    with pytest.raises(
        ValueError,
        match=re.escape(f"Geographic map bound '{name}' is out of range."),
    ):
        _parse_map_bounds(raw_bounds)
