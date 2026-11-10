#!/usr/bin/env python3
"""Check custom POI icon mappings against complete Efteling API responses."""

from __future__ import annotations

import argparse
import ast
import asyncio
import importlib
import json
import sys
from pathlib import Path
from typing import Any

import aiohttp

ROOT = Path(__file__).resolve().parents[1]
CONSTANTS_PATH = ROOT / "custom_components" / "efteling_park" / "const.py"
sys.path.insert(0, str(ROOT))
_constants = importlib.import_module("custom_components.efteling_park.const")
APP_HEADERS = _constants.APP_HEADERS
POINTS_OF_INTEREST_URL = _constants.POINTS_OF_INTEREST_URL
WAIT_TIMES_URL = _constants.WAIT_TIMES_URL


def _load_json(path: Path) -> dict[str, Any]:
    """Load a JSON API response."""
    payload = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(payload, dict):
        msg = f"{path} must contain a JSON object."
        raise TypeError(msg)

    return payload


async def _fetch_json(url: str) -> dict[str, Any]:
    """Fetch a JSON API response."""
    timeout = aiohttp.ClientTimeout(total=10)

    async with (
        aiohttp.ClientSession(timeout=timeout) as session,
        session.get(url, headers=APP_HEADERS) as response,
    ):
        response.raise_for_status()
        payload = await response.json()

    if not isinstance(payload, dict):
        msg = f"{url} must return a JSON object."
        raise TypeError(msg)

    return payload


def _load_icon_mappings() -> tuple[dict[str, str], dict[str, str]]:
    """Read the literal icon dictionaries from const.py."""
    syntax_tree = ast.parse(CONSTANTS_PATH.read_text(encoding="utf-8"))
    mappings: dict[str, dict[str, str]] = {}

    for statement in syntax_tree.body:
        if (
            isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and statement.target.id
            in {
                "CUSTOM_ATTRACTION_ICONS",
                "CUSTOM_SHOW_ICONS",
            }
        ):
            if statement.value is None:
                msg = f"{statement.target.id} must have a dictionary value."
                raise ValueError(msg)

            value = ast.literal_eval(statement.value)

            if not isinstance(value, dict):
                msg = f"{statement.target.id} must be a dictionary."
                raise TypeError(msg)

            mappings[statement.target.id] = value

    attraction_icons = mappings.get("CUSTOM_ATTRACTION_ICONS")
    show_icons = mappings.get("CUSTOM_SHOW_ICONS")

    if attraction_icons is None or show_icons is None:
        msg = "Could not find both custom icon dictionaries in const.py."
        raise ValueError(msg)

    return attraction_icons, show_icons


def _poi_ids_by_category(
    payload: dict[str, Any],
) -> dict[str, set[str]]:
    """Return POI IDs, including alternate IDs, grouped by category."""
    hits = payload.get("hits")

    if not isinstance(hits, dict):
        msg = "POI response is missing the hits object."
        raise TypeError(msg)

    records = hits.get("hit")

    if not isinstance(records, list):
        msg = "POI response is missing the hits.hit list."
        raise TypeError(msg)

    result = {
        "attraction": set(),
        "show": set(),
    }

    for record in records:
        if not isinstance(record, dict):
            continue

        fields = record.get("fields")

        if not isinstance(fields, dict):
            continue

        category = fields.get("category")

        if category not in result:
            continue

        for field in ("id", "alternateid"):
            poi_id = fields.get(field)

            if isinstance(poi_id, str) and poi_id:
                result[category].add(poi_id)

    return result


def _wait_time_ids(payload: dict[str, Any]) -> set[str]:
    """Return all IDs exposed by the live wait-time endpoint."""
    records = payload.get("AttractionInfo")

    if not isinstance(records, list):
        msg = "Wait-time response is missing the AttractionInfo list."
        raise TypeError(msg)

    return {
        record["Id"]
        for record in records
        if isinstance(record, dict)
        and isinstance(record.get("Id"), str)
        and record["Id"]
    }


def _invalid_icon_mappings(
    mappings: dict[str, str],
) -> list[str]:
    """Return icon mappings with invalid IDs or icon prefixes."""
    return sorted(
        poi_id
        for poi_id, icon in mappings.items()
        if (
            not poi_id.isascii()
            or not poi_id.isalnum()
            or poi_id != poi_id.lower()
            or not icon.startswith("mdi:")
            or not icon.removeprefix("mdi:")
        )
    )


def main() -> int:
    """Run the icon mapping audit."""
    parser = argparse.ArgumentParser(
        description=(
            "Find current attractions and shows without a custom icon mapping."
        )
    )
    parser.add_argument(
        "--poi-response",
        type=Path,
        help="Path to a POI API response JSON file; fetch live if omitted.",
    )
    parser.add_argument(
        "--wait-times-response",
        type=Path,
        help="Path to a wait-times API response JSON file; fetch live if omitted.",
    )
    args = parser.parse_args()

    try:
        poi_payload = (
            _load_json(args.poi_response)
            if args.poi_response
            else asyncio.run(_fetch_json(POINTS_OF_INTEREST_URL))
        )
        wait_times_payload = (
            _load_json(args.wait_times_response)
            if args.wait_times_response
            else asyncio.run(_fetch_json(WAIT_TIMES_URL))
        )
        attraction_icons, show_icons = _load_icon_mappings()

        poi_ids = _poi_ids_by_category(poi_payload)
        wait_time_ids = _wait_time_ids(wait_times_payload)

        available_attractions = poi_ids["attraction"] & wait_time_ids
        available_shows = poi_ids["show"] & wait_time_ids

        invalid = [
            *_invalid_icon_mappings(attraction_icons),
            *_invalid_icon_mappings(show_icons),
        ]

        missing_attractions = sorted(available_attractions - set(attraction_icons))
        missing_shows = sorted(available_shows - set(show_icons))

    except (OSError, json.JSONDecodeError, TypeError, ValueError) as err:
        parser.error(str(err))

    if invalid:
        sys.stdout.write("Invalid icon mappings:\n")
        for poi_id in invalid:
            sys.stdout.write(f"  {poi_id}\n")

    if missing_attractions:
        sys.stdout.write("Current attractions without custom icons:\n")
        for poi_id in missing_attractions:
            sys.stdout.write(f"  {poi_id}\n")

    if missing_shows:
        sys.stdout.write("Current shows without custom icons:\n")
        for poi_id in missing_shows:
            sys.stdout.write(f"  {poi_id}\n")

    if invalid or missing_attractions or missing_shows:
        return 1

    sys.stdout.write("All current attractions and shows have custom icon mappings.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
