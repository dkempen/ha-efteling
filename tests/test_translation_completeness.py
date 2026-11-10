"""Tests for Efteling translation completeness."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from custom_components.efteling_park.binary_sensor.annual_passes import (
    ANNUAL_PASS_DESCRIPTIONS,
)
from custom_components.efteling_park.binary_sensor.park_event import (
    PARK_EVENT_BINARY_SENSOR_DESCRIPTIONS,
)
from custom_components.efteling_park.binary_sensor.park_status import (
    PARK_STATUS_BINARY_SENSOR_DESCRIPTION,
)
from custom_components.efteling_park.sensor.attraction import (
    ENTITY_DESCRIPTION_ATTRACTION_WAIT_TIME,
    ENTITY_DESCRIPTION_STATUS,
)
from custom_components.efteling_park.sensor.park import PARK_SENSOR_DESCRIPTIONS
from custom_components.efteling_park.sensor.show import (
    ENTITY_DESCRIPTION_SHOW_START_TIME,
)

if TYPE_CHECKING:
    from collections.abc import Iterable


TRANSLATIONS_DIR = (
    Path(__file__).parent.parent
    / "custom_components"
    / "efteling_park"
    / "translations"
)


def _load_translation(language: str) -> dict[str, Any]:
    """Load one integration translation file."""
    path = TRANSLATIONS_DIR / f"{language}.json"

    return json.loads(path.read_text(encoding="utf-8"))


def _key_structure(value: Any) -> Any:
    """Return the nested key structure without translated values."""
    if isinstance(value, dict):
        return tuple(
            (key, _key_structure(child)) for key, child in sorted(value.items())
        )

    if isinstance(value, list):
        return tuple(_key_structure(child) for child in value)

    return None


def _translation_keys(descriptions: Iterable[Any]) -> set[str]:
    """Extract all non-empty translation keys from entity descriptions."""
    return {
        description.translation_key
        for description in descriptions
        if description.translation_key
    }


def _image_translation_key() -> str:
    """Read the map entity's declared key before Home Assistant wraps it."""
    source_path = (
        Path(__file__).parent.parent
        / "custom_components"
        / "efteling_park"
        / "image"
        / "park_map.py"
    )
    module = ast.parse(source_path.read_text(encoding="utf-8"))
    image_class = next(
        node
        for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == "EftelingParkMapImage"
    )
    assignment = next(
        node
        for node in image_class.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "_attr_translation_key"
            for target in node.targets
        )
    )
    key = ast.literal_eval(assignment.value)
    assert isinstance(key, str)
    return key


def test_english_and_dutch_translation_structures_match() -> None:
    """Require every English translation key to have a Dutch counterpart."""
    english = _load_translation("en")
    dutch = _load_translation("nl")

    assert _key_structure(english) == _key_structure(dutch)


def test_all_entity_translation_keys_exist_in_both_languages() -> None:
    """Ensure all entity descriptions have translations in both languages."""
    descriptions = {
        "sensor": (
            ENTITY_DESCRIPTION_ATTRACTION_WAIT_TIME,
            ENTITY_DESCRIPTION_STATUS,
            ENTITY_DESCRIPTION_SHOW_START_TIME,
            *PARK_SENSOR_DESCRIPTIONS,
        ),
        "binary_sensor": (
            *ANNUAL_PASS_DESCRIPTIONS,
            *PARK_EVENT_BINARY_SENSOR_DESCRIPTIONS,
            PARK_STATUS_BINARY_SENSOR_DESCRIPTION,
        ),
        "image": (),
    }

    required_keys = {
        "sensor": _translation_keys(descriptions["sensor"]),
        "binary_sensor": _translation_keys(descriptions["binary_sensor"]),
        "image": {_image_translation_key()},
    }

    for language in ("en", "nl"):
        translation = _load_translation(language)
        entity_translations = translation["entity"]

        for platform, keys in required_keys.items():
            available_keys = set(entity_translations[platform])

            assert keys <= available_keys, (
                f"Missing {language} {platform} translations: "
                f"{sorted(keys - available_keys)}"
            )
