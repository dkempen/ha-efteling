"""Shared helpers for POI-backed sensors."""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from math import isfinite
from typing import TYPE_CHECKING, ClassVar
from urllib.parse import urljoin

if TYPE_CHECKING:
    from custom_components.efteling_park.map import ParkMapMetadata
    from custom_components.efteling_park.models import Poi

MIN_LATITUDE = -90.0
MAX_LATITUDE = 90.0
MIN_LONGITUDE = -180.0
MAX_LONGITUDE = 180.0


@dataclass(frozen=True)
class PoiMetadata:
    """Normalized values derived from a POI record."""

    empire: str
    description: str
    subtitle: str | None
    latitude: float | None
    longitude: float | None
    image: str
    image_detail: str
    properties: list[str] | None
    entry_requirements: list[str] | None
    stimuli: list[str] | None
    targetgroups: list[str] | None
    type: str


@dataclass(frozen=True)
class PoiMapPosition:
    """Map position derived from POI coordinates and map metadata."""

    map_x: float | None
    map_y: float | None
    map_marker: bool


def _as_string(value: str | None) -> str:
    """Return a string value or an empty string when it is absent."""
    return value or ""


def _image_url(value: str | None) -> str:
    """Return an absolute image URL for a relative or absolute API value."""
    if not value or not value.strip():
        return ""
    return urljoin("https://www.efteling.com", value.strip())


def _string_list(value: list[str] | None) -> list[str] | None:
    """Return the string list, or None when the field is unavailable."""
    return value


def parse_poi_metadata(poi: Poi) -> PoiMetadata:
    """Normalize API-supplied POI metadata independently of map metadata."""
    latitude, longitude = _parse_coordinates(poi.get("latlon"))

    return PoiMetadata(
        empire=_as_string(poi.get("empire")),
        description=clean_html(poi.get("detail_text")),
        subtitle=poi.get("subtitle"),
        latitude=latitude,
        longitude=longitude,
        image=_image_url(poi.get("image")),
        image_detail=_image_url(poi.get("image_detailview1")),
        properties=_string_list(poi.get("properties")),
        entry_requirements=_string_list(poi.get("properties_entry_requirements")),
        stimuli=_string_list(poi.get("properties_stimuli")),
        targetgroups=_string_list(poi.get("targetgroups")),
        type=_as_string(poi.get("type")),
    )


def parse_poi_map_position(
    latitude: float | None,
    longitude: float | None,
    alternate_id: str | None,
    map_metadata: ParkMapMetadata | None,
    *,
    poi_id: str,
) -> PoiMapPosition:
    """Calculate map coordinates independently of other POI metadata."""
    position = (
        map_metadata.map_position(latitude, longitude)
        if map_metadata is not None
        else None
    )

    return PoiMapPosition(
        map_x=position[0] if position is not None else None,
        map_y=position[1] if position is not None else None,
        map_marker=position is not None and alternate_id != poi_id,
    )


def clean_html(value: str | None) -> str:
    """Remove HTML tags and normalize paragraph spacing."""
    if not value:
        return ""

    parser = _PoiHtmlTextParser()
    parser.feed(value)
    parser.close()
    text = "".join(parser.parts).replace("\xa0", " ")

    return "\n".join(part.strip() for part in text.splitlines() if part.strip())


def _parse_coordinates(value: str | None) -> tuple[float | None, float | None]:
    """Return a finite, in-range geographic coordinate pair."""
    if value is None:
        return None, None

    latitude_raw, separator, longitude_raw = value.partition(",")
    if not separator or "," in longitude_raw:
        return None, None

    try:
        latitude = float(latitude_raw.strip())
        longitude = float(longitude_raw.strip())
    except ValueError:
        return None, None

    if (
        not isfinite(latitude)
        or not isfinite(longitude)
        or not MIN_LATITUDE <= latitude <= MAX_LATITUDE
        or not MIN_LONGITUDE <= longitude <= MAX_LONGITUDE
    ):
        return None, None

    return latitude, longitude


class _PoiHtmlTextParser(HTMLParser):
    """Extract POI text while preserving structural line breaks."""

    _BLOCK_TAGS: ClassVar[frozenset[str]] = frozenset(
        {"br", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "p"}
    )
    _IGNORED_TAGS: ClassVar[frozenset[str]] = frozenset({"script", "style"})

    def __init__(self) -> None:
        """Initialize the parser."""
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(
        self,
        tag: str,
        _attrs: list[tuple[str, str | None]],
    ) -> None:
        """Start a block or ignored content region."""
        if tag in self._IGNORED_TAGS:
            self._ignored_depth += 1
        elif not self._ignored_depth and tag in self._BLOCK_TAGS:
            self._append_line_break()

    def handle_endtag(self, tag: str) -> None:
        """End a block or ignored content region."""
        if tag in self._IGNORED_TAGS:
            self._ignored_depth = max(0, self._ignored_depth - 1)
        elif not self._ignored_depth and tag in self._BLOCK_TAGS:
            self._append_line_break()

    def handle_data(self, data: str) -> None:
        """Collect visible text outside script and style elements."""
        if not self._ignored_depth:
            self.parts.append(data)

    def _append_line_break(self) -> None:
        """Add one structural line break without introducing blank lines."""
        if self.parts and not self.parts[-1].endswith("\n"):
            self.parts.append("\n")
