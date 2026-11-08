"""Tests for Efteling map markers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from custom_components.efteling_park.map import ParkMapMetadata
from custom_components.efteling_park.sensor.utils import parse_poi_metadata

if TYPE_CHECKING:
    from custom_components.efteling_park.models import Poi


def _map_metadata() -> ParkMapMetadata:
    """Return map metadata using the current Efteling map bounds."""
    return ParkMapMetadata(
        manifest={
            "summer": datetime(2026, 11, 6, 22, 22, 12, tzinfo=UTC),
            "winter": datetime(2026, 11, 6, 22, 22, 18, tzinfo=UTC),
        },
        bounds={
            "min_latitude": 51.64599309,
            "max_latitude": 51.65379826,
            "min_longitude": 5.04264951,
            "max_longitude": 5.05522907,
        },
        rotation_degrees=90,
    )


@pytest.fixture
def python_poi() -> Poi:
    """Return the Python POI with its alternate Single Rider ID."""
    return {
        "id": "python",
        "name": "Python",
        "category": "attraction",
        "alternateid": "pythonsinglerider",
        "alternatelabel": "Single rider",
        "latlon": "51.647575,5.053534",
    }


@pytest.mark.parametrize(
    "poi_id",
    [
        "python",
        "pythonsinglerider",
    ],
)
def test_map_marker_for_primary_and_alternate_poi(
    python_poi: Poi,
    poi_id: str,
) -> None:
    """Only the primary attraction should receive a map marker."""
    metadata = parse_poi_metadata(
        python_poi,
        _map_metadata(),
        poi_id=poi_id,
    )

    assert metadata.map_marker is (poi_id == "python")
    assert metadata.map_x is not None
    assert metadata.map_y is not None


def test_show_receives_map_marker() -> None:
    """Shows with valid coordinates should receive map markers."""
    poi: Poi = {
        "id": "aquanura",
        "name": "Aquanura",
        "category": "show",
        "latlon": "51.648014,5.045388",
    }

    metadata = parse_poi_metadata(
        poi,
        _map_metadata(),
        poi_id="aquanura",
    )

    assert metadata.map_marker is True
    assert metadata.map_x is not None
    assert metadata.map_y is not None


@pytest.mark.parametrize(
    "coordinates",
    [
        None,
        "invalid",
        "51.660000,5.060000",
    ],
)
def test_map_marker_requires_valid_in_bounds_coordinates(
    coordinates: str | None,
) -> None:
    """POIs without valid coordinates inside the map must not be markers."""
    poi: Poi = {
        "id": "python",
        "name": "Python",
        "category": "attraction",
    }

    if coordinates is not None:
        poi["latlon"] = coordinates

    metadata = parse_poi_metadata(
        poi,
        _map_metadata(),
        poi_id="python",
    )

    assert metadata.map_marker is False
    assert metadata.map_x is None
    assert metadata.map_y is None
