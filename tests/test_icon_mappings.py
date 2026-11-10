"""Tests for the dynamic attraction and show icon mappings."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

from custom_components.efteling_park.const import (
    CUSTOM_ATTRACTION_ICONS,
    CUSTOM_SHOW_ICONS,
)

_SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "check_icons.py"
_SPEC = importlib.util.spec_from_file_location("check_icons", _SCRIPT_PATH)
assert _SPEC is not None
assert _SPEC.loader is not None
_CHECK_ICONS = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_CHECK_ICONS)

_load_icon_mappings = vars(_CHECK_ICONS)["_load_icon_mappings"]
_poi_ids_by_category = vars(_CHECK_ICONS)["_poi_ids_by_category"]
_wait_time_ids = vars(_CHECK_ICONS)["_wait_time_ids"]
_invalid_icon_mappings = vars(_CHECK_ICONS)["_invalid_icon_mappings"]


def test_custom_icon_mappings_use_normalized_ids_and_mdi_icons() -> None:
    """Require normalized POI IDs and valid MDI-style icon identifiers."""
    for mappings in (
        CUSTOM_ATTRACTION_ICONS,
        CUSTOM_SHOW_ICONS,
    ):
        assert mappings

        for poi_id, icon in mappings.items():
            assert poi_id.isascii()
            assert poi_id.isalnum()
            assert poi_id == poi_id.lower()
            assert icon.startswith("mdi:")
            assert len(icon.removeprefix("mdi:")) > 0


def test_representative_attraction_and_show_icons_are_reachable() -> None:
    """Protect icon overrides used by the captured API examples."""
    assert CUSTOM_ATTRACTION_ICONS["python"] == "mdi:snake"
    assert CUSTOM_ATTRACTION_ICONS["pythonsinglerider"] == "mdi:snake"
    assert CUSTOM_SHOW_ICONS["aquanura"] == "mdi:fountain"


def test_load_icon_mappings_reads_both_const_dictionaries() -> None:
    """Load both mapping dictionaries from the integration constants."""
    assert _load_icon_mappings() == (
        CUSTOM_ATTRACTION_ICONS,
        CUSTOM_SHOW_ICONS,
    )


def test_poi_ids_by_category_includes_alternate_ids() -> None:
    """Collect attraction and show primary and alternate IDs."""
    payload = {
        "hits": {
            "hit": [
                {
                    "fields": {
                        "category": "attraction",
                        "id": "python",
                        "alternateid": "altpython",
                    }
                },
                {"fields": {"category": "show", "id": "aquanura"}},
                {"fields": {"category": "other", "id": "ignored"}},
            ]
        }
    }
    assert _poi_ids_by_category(payload) == {
        "attraction": {"python", "altpython"},
        "show": {"aquanura"},
    }


def test_wait_time_ids_extracts_valid_identifiers() -> None:
    """Ignore malformed wait-time records and return non-empty string IDs."""
    assert _wait_time_ids(
        {"AttractionInfo": [{"Id": "python"}, {"Id": ""}, {"Id": 1}, None]}
    ) == {"python"}


@pytest.mark.parametrize(
    "mapping",
    [
        {"UPPER": "mdi:snake"},
        {"not-valid": "mdi:snake"},
        {"python": "snake"},
        {"python": "mdi:"},
    ],
)
def test_invalid_icon_mappings_detects_bad_ids_and_prefixes(
    mapping: dict[str, str],
) -> None:
    """Identify identifiers and icon values outside the mapping contract."""
    assert _invalid_icon_mappings(mapping)


def test_captured_api_pois_have_custom_icon_mappings(
    api_response_payloads: tuple[dict[str, Any], dict[str, Any], dict[str, Any]],
    annual_pass_response_payload: dict[str, dict[str, bool]],
) -> None:
    """Keep fixture-backed current attraction and show IDs mapped."""
    del annual_pass_response_payload
    poi_payload, wait_payload, _ = api_response_payloads
    poi_ids = _poi_ids_by_category(poi_payload)
    wait_ids = _wait_time_ids(wait_payload)
    assert not (poi_ids["attraction"] & wait_ids - set(CUSTOM_ATTRACTION_ICONS))
    assert not (poi_ids["show"] & wait_ids - set(CUSTOM_SHOW_ICONS))
