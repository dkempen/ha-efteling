"""Tests for Efteling park map metadata and coordinates."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.efteling_park.map import (
    MAP_MANIFEST_URL,
    ParkMapMetadata,
    _parse_map_bounds,
    async_get_park_map_metadata,
    parse_map_manifest,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


MIN_LATITUDE = 51.64599309
MAX_LATITUDE = 51.65379826
MIN_LONGITUDE = 5.04264951
MAX_LONGITUDE = 5.05522907

MAP_BOUNDS = {
    "min_latitude": MIN_LATITUDE,
    "max_latitude": MAX_LATITUDE,
    "min_longitude": MIN_LONGITUDE,
    "max_longitude": MAX_LONGITUDE,
}


def _map_metadata(rotation_degrees: int = 90) -> ParkMapMetadata:
    """Return map metadata using the current Efteling map bounds."""
    return ParkMapMetadata(
        manifest={
            "summer": datetime(2026, 11, 6, 22, 22, 12, tzinfo=UTC),
            "winter": datetime(2026, 11, 6, 22, 22, 18, tzinfo=UTC),
        },
        bounds=MAP_BOUNDS,
        rotation_degrees=rotation_degrees,
    )


def test_rotated_map_position() -> None:
    """Convert geographic corners and center into positions on the rotated image."""
    map_metadata = _map_metadata()

    assert map_metadata.map_position(MAX_LATITUDE, MAX_LONGITUDE) == (0, 0)
    assert map_metadata.map_position(MIN_LATITUDE, MAX_LONGITUDE) == (100, 0)
    assert map_metadata.map_position(MAX_LATITUDE, MIN_LONGITUDE) == (0, 100)
    assert map_metadata.map_position(MIN_LATITUDE, MIN_LONGITUDE) == (100, 100)

    assert map_metadata.map_position(
        (MIN_LATITUDE + MAX_LATITUDE) / 2,
        (MIN_LONGITUDE + MAX_LONGITUDE) / 2,
    ) == (50, 50)


def test_north_up_map_position() -> None:
    """Use conventional longitude/latitude orientation for an unrotated map."""
    map_metadata = _map_metadata(rotation_degrees=0)

    assert map_metadata.map_position(MAX_LATITUDE, MIN_LONGITUDE) == (0, 0)
    assert map_metadata.map_position(MIN_LATITUDE, MAX_LONGITUDE) == (100, 100)


@pytest.mark.parametrize(
    ("rotation", "expected"),
    [
        (180, (0, 100)),
        (270, (100, 100)),
        (45, None),
    ],
)
def test_map_position_supports_rotations(
    rotation: int,
    expected: tuple[float, float] | None,
) -> None:
    """Rotate the coordinate mapping or reject unsupported rotations."""
    assert _map_metadata(rotation).map_position(MAX_LATITUDE, MAX_LONGITUDE) == expected


def test_map_position_rejects_missing_bounds_and_non_finite_coordinates() -> None:
    """Return no map position without bounds or with infinite coordinates."""
    metadata = _map_metadata()
    no_bounds = ParkMapMetadata(metadata.manifest, None, metadata.rotation_degrees)

    assert no_bounds.map_position(51.65, 5.05) is None
    assert metadata.map_position(float("inf"), 5.05) is None
    assert metadata.map_position(51.65, float("nan")) is None


def test_parse_map_manifest_accepts_optional_metadata() -> None:
    """Use default rotation and omit bounds when optional manifest fields are absent."""
    metadata = parse_map_manifest(
        {
            "summer": {"updated_at": "2026-11-06T22:22:12Z"},
            "winter": {"updated_at": "2026-11-06T22:22:18Z"},
        }
    )

    assert metadata.bounds is None
    assert metadata.rotation_degrees == 90
    assert metadata.manifest["summer"].isoformat() == "2026-11-06T22:22:12+00:00"


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_parse_map_manifest_accepts_supported_rotation(rotation: int) -> None:
    """Preserve a supported rotation explicitly provided by the manifest."""
    metadata = parse_map_manifest(
        {
            "summer": {"updated_at": "2026-11-06T22:22:12Z"},
            "winter": {"updated_at": "2026-11-06T22:22:18Z"},
            "rotation_degrees": rotation,
        }
    )

    assert metadata.rotation_degrees == rotation


@pytest.mark.parametrize(
    ("raw_manifest", "error", "message"),
    [
        ([], TypeError, "Invalid Efteling map manifest"),
        (
            {"summer": [], "winter": {}},
            TypeError,
            "Invalid map manifest data for summer",
        ),
        (
            {"summer": {}, "winter": {"updated_at": "2026-11-06T22:22:18Z"}},
            TypeError,
            "Invalid map update timestamp for summer",
        ),
        (
            {
                "summer": {"updated_at": 123},
                "winter": {"updated_at": "2026-11-06T22:22:18Z"},
            },
            TypeError,
            "Invalid map update timestamp for summer",
        ),
        (
            {
                "summer": {"updated_at": "bad"},
                "winter": {"updated_at": "2026-11-06T22:22:18Z"},
            },
            ValueError,
            "Invalid map update timestamp for summer",
        ),
    ],
)
def test_parse_map_manifest_rejects_invalid_manifest(
    raw_manifest: object,
    error: type[Exception],
    message: str,
) -> None:
    """Reject malformed top-level, seasonal, and timestamp data."""
    with pytest.raises(error, match=message):
        parse_map_manifest(raw_manifest)


@pytest.mark.parametrize(
    ("rotation", "error"),
    [
        (True, TypeError),
        ("90", TypeError),
        (45, ValueError),
    ],
)
def test_parse_map_manifest_rejects_invalid_rotation(
    rotation: object,
    error: type[Exception],
) -> None:
    """Reject rotations that are not supported integer values."""
    with pytest.raises(error, match="rotation_degrees"):
        parse_map_manifest(
            {
                "summer": {"updated_at": "2026-11-06T22:22:12Z"},
                "winter": {"updated_at": "2026-11-06T22:22:18Z"},
                "rotation_degrees": rotation,
            }
        )


async def test_async_get_park_map_metadata_parses_response(
    hass: HomeAssistant,
) -> None:
    """Fetch and parse the map manifest from the shared client session."""
    response = MagicMock()
    response.text = AsyncMock(
        return_value=json.dumps(
            {
                "summer": {"updated_at": "2026-11-06T22:22:12Z"},
                "winter": {"updated_at": "2026-11-06T22:22:18Z"},
            }
        )
    )
    response.raise_for_status = MagicMock()
    request = MagicMock()
    request.__aenter__ = AsyncMock(return_value=response)
    request.__aexit__ = AsyncMock(return_value=None)
    session = MagicMock()
    session.get.return_value = request

    with patch(
        "custom_components.efteling_park.map.async_get_clientsession",
        return_value=session,
    ):
        metadata = await async_get_park_map_metadata(hass)

    assert metadata is not None
    assert metadata.rotation_degrees == 90
    session.get.assert_called_once_with(MAP_MANIFEST_URL)


@pytest.mark.parametrize(
    "failure",
    [
        aiohttp.ClientError,
        TimeoutError,
        TypeError,
        ValueError,
    ],
)
async def test_async_get_park_map_metadata_returns_none_on_failure(
    hass: HomeAssistant,
    failure: type[Exception],
) -> None:
    """Treat request and manifest failures as unavailable supplementary metadata."""
    session = MagicMock()
    session.get.side_effect = failure("map request failed")

    with patch(
        "custom_components.efteling_park.map.async_get_clientsession",
        return_value=session,
    ):
        assert await async_get_park_map_metadata(hass) is None


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [
        (None, 5.05),
        (51.65, None),
        (51.66, 5.05),
        (51.65, 5.06),
        (-91, 5.05),
    ],
)
def test_map_position_returns_none_for_invalid_coordinates(
    latitude: float | None,
    longitude: float | None,
) -> None:
    """Return no position for missing or out-of-map coordinates."""
    assert _map_metadata().map_position(latitude, longitude) is None


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
