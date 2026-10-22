"""Shared helpers for POI-backed sensors."""

from __future__ import annotations

import html
import re
from contextlib import suppress
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urljoin

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
    """Normalize API-supplied POI metadata once for an entity update."""
    latitude: float | None = None
    longitude: float | None = None
    coordinates = poi.get("latlon")
    if coordinates and "," in coordinates:
        latitude_raw, _, longitude_raw = coordinates.partition(",")
        with suppress(ValueError):
            latitude = float(latitude_raw.strip())
            longitude = float(longitude_raw.strip())

    subtitle = poi.get("subtitle")
    return PoiMetadata(
        empire=_as_string(poi.get("empire")),
        description=clean_html(poi.get("detail_text")),
        subtitle=subtitle,
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


def clean_html(value: str | None) -> str:
    """Remove HTML tags and normalize paragraph spacing."""
    if not value:
        return ""
    text = html.unescape(value).replace("\xa0", " ")
    text = re.sub(
        r"<br\s*/?>|</p\s*>\s*<p\b[^>]*>",
        "\n",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s*\n\s*", "\n", text).strip()
