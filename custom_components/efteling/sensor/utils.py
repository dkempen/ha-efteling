"""Shared sensor helpers."""

import html
import re
from contextlib import suppress
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from custom_components.efteling.models import Poi


@dataclass(frozen=True)
class PoiMetadata:
    """Normalized values shared by POI-backed sensors."""

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


def parse_poi_metadata(poi: Poi) -> PoiMetadata:
    """Normalize API-supplied POI metadata once for an update."""
    latitude: float | None = None
    longitude: float | None = None
    coordinates = poi.get("latlon")
    if isinstance(coordinates, str) and "," in coordinates:
        latitude_raw, _, longitude_raw = coordinates.partition(",")
        with suppress(ValueError):
            latitude, longitude = float(latitude_raw), float(longitude_raw)

    def image_url(value: object) -> str:
        return f"https://www.efteling.com{value}" if isinstance(value, str) else ""

    def string_list(value: object) -> list[str] | None:
        if not isinstance(value, list):
            return None
        return [item for item in value if isinstance(item, str)]

    subtitle = poi.get("subtitle")
    return PoiMetadata(
        empire=str(poi.get("empire", "")),
        description=clean_html(poi.get("detail_text", "")),
        subtitle=subtitle if isinstance(subtitle, str) else None,
        latitude=latitude,
        longitude=longitude,
        image=image_url(poi.get("image")),
        image_detail=image_url(poi.get("image_detailview1")),
        properties=string_list(poi.get("properties")),
        entry_requirements=string_list(poi.get("properties_entry_requirements")),
        stimuli=string_list(poi.get("properties_stimuli")),
        targetgroups=string_list(poi.get("targetgroups")),
        type=str(poi.get("type", "")),
    )


def clean_html(text: str) -> str:
    """Remove HTML tags and normalize paragraph spacing."""
    text = html.unescape(text).replace("\xa0", " ")
    text = re.sub(
        r"<br\s*/?>|</p\s*>\s*<p\b[^>]*>",
        "\n",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s*\n\s*", "\n", text).strip()
