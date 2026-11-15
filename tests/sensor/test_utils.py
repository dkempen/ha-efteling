"""Tests for Efteling POI metadata and map position utilities."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from custom_components.efteling_park.map import ParkMapMetadata
from custom_components.efteling_park.sensor.utils import (
    clean_html,
    parse_poi_map_position,
    parse_poi_metadata,
)

if TYPE_CHECKING:
    from custom_components.efteling_park.models import Poi


def _map_metadata(rotation_degrees: int = 90) -> ParkMapMetadata:
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
        rotation_degrees=rotation_degrees,
    )


def test_parse_poi_metadata_normalizes_coordinates_and_urls() -> None:
    """Parse valid coordinates and normalize relative and absolute image URLs."""
    result = parse_poi_metadata(
        {
            "id": "python",
            "name": "Python",
            "category": "attraction",
            "empire": "Anderrijk",
            "detail_text": "<p>A &amp; B</p><p>Coaster</p>",
            "latlon": "51.65, 5.05",
            "image": "/images/python.jpg",
            "image_detailview1": "https://example.test/detail.jpg",
            "properties": ["fast"],
            "properties_entry_requirements": ["1.20m"],
            "properties_stimuli": ["height"],
            "targetgroups": ["families"],
            "type": "rollercoaster",
        }
    )
    assert result.empire == "Anderrijk"
    assert result.description == "A & B\nCoaster"
    assert (result.latitude, result.longitude) == (51.65, 5.05)
    assert result.image == "https://www.efteling.com/images/python.jpg"
    assert result.image_detail == "https://example.test/detail.jpg"
    assert result.properties == ["fast"]
    assert result.entry_requirements == ["1.20m"]
    assert result.stimuli == ["height"]
    assert result.targetgroups == ["families"]


def test_parse_poi_metadata_handles_empty_and_invalid_metadata() -> None:
    """Use empty defaults when optional metadata is absent or malformed."""
    result = parse_poi_metadata(
        {
            "id": "python",
            "name": "Python",
            "category": "attraction",
            "latlon": "invalid,coordinates",
            "image": "  ",
            "image_detailview1": None,
            "detail_text": None,
        }
    )
    assert result.empire == ""
    assert result.description == ""
    assert result.latitude is None
    assert result.longitude is None
    assert result.image == ""
    assert result.image_detail == ""
    assert result.properties is None
    assert result.type == ""


def test_parse_poi_metadata_handles_invalid_coordinate_pair() -> None:
    """Reject the complete coordinate pair when either value is invalid."""
    result = parse_poi_metadata(
        {
            "id": "python",
            "name": "Python",
            "category": "attraction",
            "latlon": "51.65, west",
        }
    )
    assert result.latitude is None
    assert result.longitude is None


@pytest.mark.parametrize(
    "coordinates",
    ["NaN,5", "Infinity,5", "91,5", "51,181", "51,5,6", "51.65, west"],
)
def test_parse_poi_metadata_rejects_invalid_geographic_coordinates(
    coordinates: str,
) -> None:
    """Reject non-finite, malformed, and out-of-range coordinate pairs."""
    result = parse_poi_metadata(
        {
            "id": "python",
            "name": "Python",
            "category": "attraction",
            "latlon": coordinates,
        }
    )

    assert (result.latitude, result.longitude) == (None, None)


def test_clean_html_unescapes_entities_and_normalizes_breaks() -> None:
    """Clean tags, paragraph boundaries, entities, and whitespace."""
    assert clean_html(" <p>A&nbsp;&amp; B</p> <p>C<br/>D</p> ") == "A & B\nC\nD"
    assert clean_html("") == ""


def test_clean_html_preserves_blocks_and_omits_script_and_style() -> None:
    """Extract nested visible text with block boundaries and no executable text."""
    assert (
        clean_html(
            "<div>A <b>nested</b></div><ul><li>One</li><li>Two</li></ul>"
            "<script>bad()</script><style>.hidden {}</style>"
        )
        == "A nested\nOne\nTwo"
    )


def test_clean_html_handles_empty_and_structured_content() -> None:
    """Remove ignored content and preserve meaningful block boundaries."""
    assert clean_html(None) == ""
    assert clean_html("") == ""
    assert (
        clean_html(
            "<p>Ride&nbsp;<strong>description</strong></p>"
            "<script>ignored script</script>"
            "<style>ignored style</style>"
            "<div>Second line</div>"
        )
        == "Ride description\nSecond line"
    )


def test_parse_poi_metadata_keeps_api_fields_separate_from_map_fields() -> None:
    """Parse API metadata without coupling it to map metadata."""
    metadata = parse_poi_metadata(
        {
            "id": "python",
            "name": "Python",
            "category": "attraction",
            "empire": "Fantasierijk",
            "detail_text": "<p>Ride <strong>description</strong></p>",
            "subtitle": "Ride subtitle",
            "latlon": "51.647575,5.043718",
            "image": "/content/ride.jpg",
            "image_detailview1": "https://example.com/detail.jpg",
            "properties": ["indoor"],
            "properties_entry_requirements": ["minimum_height"],
            "properties_stimuli": ["darkness"],
            "targetgroups": ["families"],
            "type": "Attractie",
        }
    )

    assert metadata.empire == "Fantasierijk"
    assert metadata.description == "Ride description"
    assert metadata.subtitle == "Ride subtitle"
    assert metadata.latitude == pytest.approx(51.647575)
    assert metadata.longitude == pytest.approx(5.043718)
    assert metadata.image == "https://www.efteling.com/content/ride.jpg"
    assert metadata.image_detail == "https://example.com/detail.jpg"
    assert metadata.properties == ["indoor"]
    assert metadata.entry_requirements == ["minimum_height"]
    assert metadata.stimuli == ["darkness"]
    assert metadata.targetgroups == ["families"]
    assert metadata.type == "Attractie"
    assert not hasattr(metadata, "map_x")
    assert not hasattr(metadata, "map_y")
    assert not hasattr(metadata, "map_marker")


@pytest.mark.parametrize(
    "latlon",
    [
        None,
        "51.647575",
        "51.647575,5.043718,5.1",
        "invalid,5.043718",
        "nan,5.043718",
        "91,5.043718",
        "51.647575,181",
    ],
)
def test_parse_poi_metadata_rejects_invalid_coordinates(
    latlon: str | None,
) -> None:
    """Leave coordinates unset when the API provides invalid geographic data."""
    metadata = parse_poi_metadata(
        {
            "id": "python",
            "name": "Python",
            "category": "attraction",
            "latlon": latlon,
        }
    )

    assert metadata.latitude is None
    assert metadata.longitude is None


def test_parse_poi_metadata_defaults_missing_optional_fields() -> None:
    """Provide stable defaults when optional API metadata is missing."""
    metadata = parse_poi_metadata(
        {
            "id": "python",
            "name": "Python",
            "category": "attraction",
        }
    )

    assert metadata.empire == ""
    assert metadata.description == ""
    assert metadata.subtitle is None
    assert metadata.latitude is None
    assert metadata.longitude is None
    assert metadata.image == ""
    assert metadata.image_detail == ""
    assert metadata.properties is None
    assert metadata.entry_requirements is None
    assert metadata.stimuli is None
    assert metadata.targetgroups is None
    assert metadata.type == ""


def test_parse_poi_map_position_uses_map_metadata() -> None:
    """Calculate coordinates independently from API metadata parsing."""
    map_metadata = _map_metadata()
    position = parse_poi_map_position(
        51.647575,
        5.043718,
        None,
        map_metadata,
        poi_id="python",
    )

    expected = map_metadata.map_position(51.647575, 5.043718)
    assert expected is not None
    assert position.map_x == pytest.approx(expected[0])
    assert position.map_y == pytest.approx(expected[1])
    assert position.map_marker is True


def test_parse_poi_map_position_suppresses_alternate_poi_marker() -> None:
    """Retain coordinates but hide the map marker for an alternate POI."""
    position = parse_poi_map_position(
        51.647575,
        5.043718,
        "single_rider",
        _map_metadata(),
        poi_id="single_rider",
    )

    assert position.map_x is not None
    assert position.map_y is not None
    assert position.map_marker is False


def test_parse_poi_map_position_handles_missing_inputs() -> None:
    """Return an empty position when coordinates or map metadata are unavailable."""
    no_metadata = parse_poi_map_position(
        51.647575,
        5.043718,
        None,
        None,
        poi_id="python",
    )
    no_coordinates = parse_poi_map_position(
        None,
        5.043718,
        None,
        _map_metadata(),
        poi_id="python",
    )

    assert no_metadata.map_x is None
    assert no_metadata.map_y is None
    assert no_metadata.map_marker is False
    assert no_coordinates.map_x is None
    assert no_coordinates.map_y is None
    assert no_coordinates.map_marker is False


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
    poi_metadata = parse_poi_metadata(python_poi)
    position = parse_poi_map_position(
        poi_metadata.latitude,
        poi_metadata.longitude,
        python_poi.get("alternateid"),
        _map_metadata(),
        poi_id=poi_id,
    )

    assert position.map_marker is (poi_id == "python")
    assert position.map_x is not None
    assert position.map_y is not None


def test_show_receives_map_marker() -> None:
    """Shows with valid coordinates should receive map markers."""
    poi: Poi = {
        "id": "aquanura",
        "name": "Aquanura",
        "category": "show",
        "latlon": "51.648014,5.045388",
    }

    poi_metadata = parse_poi_metadata(poi)
    position = parse_poi_map_position(
        poi_metadata.latitude,
        poi_metadata.longitude,
        poi.get("alternateid"),
        _map_metadata(),
        poi_id="aquanura",
    )

    assert position.map_marker is True
    assert position.map_x is not None
    assert position.map_y is not None


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

    poi_metadata = parse_poi_metadata(poi)
    position = parse_poi_map_position(
        poi_metadata.latitude,
        poi_metadata.longitude,
        poi.get("alternateid"),
        _map_metadata(),
        poi_id="python",
    )

    assert position.map_marker is False
    assert position.map_x is None
    assert position.map_y is None
