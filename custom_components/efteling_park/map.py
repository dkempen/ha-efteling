"""Shared Efteling park map metadata and coordinate conversion."""

from __future__ import annotations

import asyncio
import json
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import LOGGER

if TYPE_CHECKING:
    from datetime import datetime

    from homeassistant.core import HomeAssistant

type MapSeason = Literal["summer", "winter"]
type MapBounds = dict[str, float]

MAP_BASE_URL = (
    "https://raw.githubusercontent.com/dkempen/ha-efteling/refs/heads/master/images/map"
)
MAP_MANIFEST_URL = f"{MAP_BASE_URL}/manifest.json"
MAP_IMAGE_URLS: dict[MapSeason, str] = {
    "summer": f"{MAP_BASE_URL}/summer.jpg",
    "winter": f"{MAP_BASE_URL}/winter.jpg",
}

MAP_SEASONS: tuple[MapSeason, ...] = ("summer", "winter")
SUPPORTED_ROTATIONS = frozenset({0, 90, 180, 270})
DEFAULT_ROTATION_DEGREES = 90
MAP_MANIFEST_TIMEOUT = 10


@dataclass(frozen=True)
class ParkMapMetadata:
    """Validated metadata describing the seasonal park map."""

    manifest: dict[MapSeason, datetime]
    bounds: MapBounds | None
    rotation_degrees: int

    def map_position(
        self,
        latitude: float | None,
        longitude: float | None,
    ) -> tuple[float, float] | None:
        """Convert geographic coordinates into image percentages."""
        if (
            self.bounds is None
            or latitude is None
            or longitude is None
            or not math.isfinite(latitude)
            or not math.isfinite(longitude)
        ):
            return None

        min_latitude = self.bounds["min_latitude"]
        max_latitude = self.bounds["max_latitude"]
        min_longitude = self.bounds["min_longitude"]
        max_longitude = self.bounds["max_longitude"]

        if not (
            min_latitude <= latitude <= max_latitude
            and min_longitude <= longitude <= max_longitude
        ):
            return None

        longitude_position = (longitude - min_longitude) / (
            max_longitude - min_longitude
        )
        latitude_position = (max_latitude - latitude) / (max_latitude - min_latitude)

        match self.rotation_degrees:
            case 0:
                x = longitude_position
                y = latitude_position
            case 90:
                x = latitude_position
                y = 1 - longitude_position
            case 180:
                x = 1 - longitude_position
                y = 1 - latitude_position
            case 270:
                x = 1 - latitude_position
                y = longitude_position
            case _:
                return None

        return round(x * 100, 4), round(y * 100, 4)


def _parse_map_bounds(raw_bounds: object) -> MapBounds | None:
    """Validate and parse the map's minimum and maximum coordinates."""
    if raw_bounds is None:
        return None

    if not isinstance(raw_bounds, dict):
        msg = "Map manifest geographic bounds must be an object."
        raise TypeError(msg)

    bounds: MapBounds = {}

    for name, minimum, maximum in (
        ("min_latitude", -90.0, 90.0),
        ("max_latitude", -90.0, 90.0),
        ("min_longitude", -180.0, 180.0),
        ("max_longitude", -180.0, 180.0),
    ):
        value = raw_bounds.get(name)

        if isinstance(value, bool) or not isinstance(value, (int, float)):
            msg = f"Invalid geographic map bound '{name}'."
            raise TypeError(msg)

        if not minimum <= value <= maximum:
            msg = f"Geographic map bound '{name}' is out of range."
            raise ValueError(msg)

        bounds[name] = float(value)

    if bounds["min_latitude"] >= bounds["max_latitude"]:
        msg = "Minimum map latitude must be less than maximum map latitude."
        raise ValueError(msg)

    if bounds["min_longitude"] >= bounds["max_longitude"]:
        msg = "Minimum map longitude must be less than maximum map longitude."
        raise ValueError(msg)

    return bounds


def _parse_rotation_degrees(raw_rotation: object) -> int:
    """Validate the optional map rotation value from the manifest."""
    if raw_rotation is None:
        return DEFAULT_ROTATION_DEGREES

    if isinstance(raw_rotation, bool) or not isinstance(raw_rotation, int):
        msg = "Map manifest rotation_degrees must be an integer."
        raise TypeError(msg)

    if raw_rotation not in SUPPORTED_ROTATIONS:
        msg = (
            "Map manifest rotation_degrees must be one of "
            f"{sorted(SUPPORTED_ROTATIONS)}."
        )
        raise ValueError(msg)

    return raw_rotation


def parse_map_manifest(raw_manifest: object) -> ParkMapMetadata:
    """Validate and parse the map manifest."""
    if not isinstance(raw_manifest, dict):
        msg = "Invalid Efteling map manifest."
        raise TypeError(msg)

    manifest: dict[MapSeason, datetime] = {}

    for season in MAP_SEASONS:
        season_data = raw_manifest.get(season)

        if not isinstance(season_data, dict):
            msg = f"Invalid map manifest data for {season}."
            raise TypeError(msg)

        updated_at_raw = season_data.get("updated_at")

        if not isinstance(updated_at_raw, str):
            msg = f"Invalid map update timestamp for {season}."
            raise TypeError(msg)

        updated_at = dt_util.parse_datetime(updated_at_raw)

        if updated_at is None:
            msg = f"Invalid map update timestamp for {season}."
            raise ValueError(msg)

        manifest[season] = updated_at

    return ParkMapMetadata(
        manifest=manifest,
        bounds=_parse_map_bounds(raw_manifest.get("bounds")),
        rotation_degrees=_parse_rotation_degrees(raw_manifest.get("rotation_degrees")),
    )


async def async_get_park_map_metadata(
    hass: HomeAssistant,
) -> ParkMapMetadata | None:
    """
    Fetch and parse the park map manifest.

    The map is supplementary functionality, so a failed manifest request
    should not prevent the other integration platforms from loading.
    """
    try:
        async with asyncio.timeout(MAP_MANIFEST_TIMEOUT):
            async with async_get_clientsession(hass).get(MAP_MANIFEST_URL) as response:
                response.raise_for_status()
                raw_manifest = json.loads(await response.text())

        return parse_map_manifest(raw_manifest)

    except (aiohttp.ClientError, TimeoutError, TypeError, ValueError) as err:
        LOGGER.warning(
            "Unable to load the Efteling park map manifest; "
            "map positioning will be unavailable: %s",
            err,
        )
        return None
