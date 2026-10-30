"""Tests for POI metadata normalization."""

from custom_components.efteling.sensor.utils import clean_html, parse_poi_metadata


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
    """Reject a coordinate pair when either coordinate is not numeric."""
    result = parse_poi_metadata(
        {
            "id": "python",
            "name": "Python",
            "category": "attraction",
            "latlon": "51.65, west",
        }
    )
    assert result.latitude == 51.65
    assert result.longitude is None


def test_clean_html_unescapes_entities_and_normalizes_breaks() -> None:
    """Clean tags, paragraph boundaries, entities, and whitespace."""
    assert clean_html(" <p>A&nbsp;&amp; B</p> <p>C<br/>D</p> ") == "A & B\nC\nD"
    assert clean_html("") == ""
