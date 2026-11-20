"""Annual pass restriction calendars and event builder."""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

from homeassistant.components.calendar import CalendarEntityDescription, CalendarEvent

from custom_components.efteling_park.coordinator import EftelingAnnualPassesCoordinator

from .calendar_entity import EftelingCalendarEntity

if TYPE_CHECKING:
    from custom_components.efteling_park.data import EftelingData
    from custom_components.efteling_park.models import AnnualPasses


def build_annual_pass_restriction_events(
    schedule: AnnualPasses,
    *,
    tier: str,
    language: str,
) -> list[CalendarEvent]:
    """Group consecutive dates on which an annual-pass tier is not valid."""
    restricted_dates: list[date] = []

    for date_value, availability in schedule.items():
        try:
            calendar_day = date.fromisoformat(date_value)
        except ValueError:
            continue

        if availability.get(tier) is False:
            restricted_dates.append(calendar_day)

    if not restricted_dates:
        return []

    is_dutch = language.lower().startswith("nl")
    summary = (
        f"{tier} abonnement niet geldig"
        if is_dutch
        else f"{tier} annual pass not valid"
    )

    restricted_dates.sort()
    events: list[CalendarEvent] = []
    range_start = restricted_dates[0]
    range_end = range_start

    for calendar_day in restricted_dates[1:]:
        if calendar_day == range_end + timedelta(days=1):
            range_end = calendar_day
            continue

        events.append(
            CalendarEvent(
                start=range_start,
                end=range_end + timedelta(days=1),
                summary=summary,
                uid=f"annual-pass-{tier.lower()}-{range_start.isoformat()}",
            )
        )
        range_start = calendar_day
        range_end = calendar_day

    events.append(
        CalendarEvent(
            start=range_start,
            end=range_end + timedelta(days=1),
            summary=summary,
            uid=f"annual-pass-{tier.lower()}-{range_start.isoformat()}",
        )
    )
    return events


ANNUAL_PASS_CLASSIC_CALENDAR_DESCRIPTION = CalendarEntityDescription(
    key="annual_pass_classic_blackout_dates",
    translation_key="annual_pass_classic_blackout_dates",
)


class EftelingAnnualPassClassicCalendar(
    EftelingCalendarEntity[EftelingAnnualPassesCoordinator]
):
    """Calendar containing dates when the Classic pass is not valid."""

    def __init__(self, data: EftelingData) -> None:
        """Initialize the Classic annual-pass calendar."""
        super().__init__(
            data.annual_passes_coordinator,
            description=ANNUAL_PASS_CLASSIC_CALENDAR_DESCRIPTION,
            unique_id="annual_pass_classic_blackout_dates",
        )

    def _get_events(self) -> list[CalendarEvent]:
        """Return dates when Classic pass access is restricted."""
        return build_annual_pass_restriction_events(
            self.coordinator.data,
            tier="Classic",
            language=self.hass.config.language,
        )


ANNUAL_PASS_PLUS_CALENDAR_DESCRIPTION = CalendarEntityDescription(
    key="annual_pass_plus_blackout_dates",
    translation_key="annual_pass_plus_blackout_dates",
)


class EftelingAnnualPassPlusCalendar(
    EftelingCalendarEntity[EftelingAnnualPassesCoordinator]
):
    """Calendar containing dates when the Plus pass is not valid."""

    def __init__(self, data: EftelingData) -> None:
        """Initialize the Plus annual-pass calendar."""
        super().__init__(
            data.annual_passes_coordinator,
            description=ANNUAL_PASS_PLUS_CALENDAR_DESCRIPTION,
            unique_id="annual_pass_plus_blackout_dates",
        )

    def _get_events(self) -> list[CalendarEvent]:
        """Return dates when Plus pass access is restricted."""
        return build_annual_pass_restriction_events(
            self.coordinator.data,
            tier="Plus",
            language=self.hass.config.language,
        )


ANNUAL_PASS_PREMIUM_CALENDAR_DESCRIPTION = CalendarEntityDescription(
    key="annual_pass_premium_blackout_dates",
    translation_key="annual_pass_premium_blackout_dates",
)


class EftelingAnnualPassPremiumCalendar(
    EftelingCalendarEntity[EftelingAnnualPassesCoordinator]
):
    """Calendar containing dates when the Premium pass is not valid."""

    def __init__(self, data: EftelingData) -> None:
        """Initialize the Premium annual-pass calendar."""
        super().__init__(
            data.annual_passes_coordinator,
            description=ANNUAL_PASS_PREMIUM_CALENDAR_DESCRIPTION,
            unique_id="annual_pass_premium_blackout_dates",
        )

    def _get_events(self) -> list[CalendarEvent]:
        """Return dates when Premium pass access is restricted."""
        return build_annual_pass_restriction_events(
            self.coordinator.data,
            tier="Premium",
            language=self.hass.config.language,
        )
