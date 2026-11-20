"""Tests for shared show data parsing helpers."""

from datetime import UTC, datetime

import pytest

from custom_components.efteling_park.show_utils import (
    parse_show_datetime,
    parse_show_duration,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("not-a-date", None),
        (
            "2026-11-20T14:00:00",
            datetime(2026, 11, 20, 13, 0, tzinfo=UTC),
        ),
        (
            "2026-11-20T14:00:00+01:00",
            datetime(2026, 11, 20, 13, 0, tzinfo=UTC),
        ),
    ],
)
def test_parse_show_datetime(
    value: str | None,
    expected: datetime | None,
) -> None:
    """Normalize naive and timezone-aware timestamps to UTC."""
    assert parse_show_datetime(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("unknown", None),
        (0, None),
        (-5, None),
        ("0", None),
        ("18", 18),
        (24, 24),
    ],
)
def test_parse_show_duration(value: int | str | None, expected: int | None) -> None:
    """Accept only positive integer durations."""
    assert parse_show_duration(value) == expected
