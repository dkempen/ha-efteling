"""Tests for annual pass calendar event generation."""

from typing import TYPE_CHECKING

from custom_components.efteling_park.calendar.annual_passes import (
    build_annual_pass_restriction_events,
)

if TYPE_CHECKING:
    from custom_components.efteling_park.models import AnnualPasses


def test_annual_pass_calendar_groups_consecutive_restriction_dates() -> None:
    """Group adjacent blocked dates while keeping gaps as separate events."""
    schedule: AnnualPasses = {
        "2026-11-20": {"Classic": False, "Plus": True, "Premium": None},
        "2026-11-21": {"Classic": False, "Plus": True, "Premium": True},
        "2026-11-22": {"Classic": True, "Plus": False, "Premium": True},
        "2026-11-23": {"Classic": False, "Plus": True, "Premium": True},
        "invalid-date": {"Classic": False, "Plus": True, "Premium": True},
    }

    classic_events_nl = build_annual_pass_restriction_events(
        schedule,
        tier="Classic",
        language="nl",
    )
    classic_events_en = build_annual_pass_restriction_events(
        schedule,
        tier="Classic",
        language="en",
    )

    assert classic_events_nl[0].summary == "Classic abonnement niet geldig"
    assert classic_events_en[0].summary == "Classic annual pass not valid"
