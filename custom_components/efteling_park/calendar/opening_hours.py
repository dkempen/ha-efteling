"""Efteling opening-hours calendar."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.calendar import CalendarEntityDescription, CalendarEvent

from custom_components.efteling_park.coordinator import EftelingParkInfoCoordinator
from custom_components.efteling_park.sensor.park_snapshot import (
    crowd_forecast_value,
    occupancy_forecast_value,
    opening_datetime,
)

from .calendar_entity import EftelingCalendarEntity, parse_calendar_date

if TYPE_CHECKING:
    from custom_components.efteling_park.data import EftelingData
    from custom_components.efteling_park.models import OpeningHours

OPENING_HOURS_CALENDAR_DESCRIPTION = CalendarEntityDescription(
    key="opening_hours",
    translation_key="opening_hours",
)
CROWD_LEVEL_LABELS = {
    "quiet": ("Rustig", "Quiet"),
    "normal": ("Normaal", "Normal"),
    "busy": ("Druk", "Busy"),
}


def _forecast_description(day: OpeningHours, language: str) -> str | None:
    """Format the day's crowd and occupancy forecasts for a calendar event."""
    details: list[str] = []
    is_dutch = language.lower().startswith("nl")
    crowd_level = crowd_forecast_value(day.get("Crowded"))
    crowd_label = (
        CROWD_LEVEL_LABELS.get(crowd_level) if crowd_level is not None else None
    )
    if crowd_label is not None:
        details.append(
            f"{'Drukte' if is_dutch else 'Crowd level'}: "
            f"{crowd_label[0] if is_dutch else crowd_label[1]}"
        )

    occupancy = occupancy_forecast_value(day.get("Crowdedness"))
    if occupancy is not None:
        details.append(f"{'Bezetting' if is_dutch else 'Occupancy'}: {occupancy}%")

    return "\n".join(details) or None


def build_opening_hours_events(
    opening_hours: list[OpeningHours],
    *,
    language: str,
) -> list[CalendarEvent]:
    """Build timed calendar events from the park's opening intervals."""
    events: list[CalendarEvent] = []

    for day in opening_hours:
        calendar_day = parse_calendar_date(day.get("Date"))
        if calendar_day is None:
            continue
        description = _forecast_description(day, language)

        for index, interval in enumerate(day.get("OpeningHours") or []):
            opened = opening_datetime(day, interval.get("Open"))
            closed = opening_datetime(day, interval.get("Close"))
            if opened is None or closed is None or closed <= opened:
                continue

            events.append(
                CalendarEvent(
                    start=opened,
                    end=closed,
                    summary="Efteling open",
                    description=description,
                    uid=f"efteling-open-{calendar_day.isoformat()}-{index}",
                )
            )

    return events


class EftelingOpeningHoursCalendar(EftelingCalendarEntity[EftelingParkInfoCoordinator]):
    """Calendar containing each period during which Efteling is open."""

    def __init__(self, data: EftelingData) -> None:
        """Initialize the opening-hours calendar."""
        super().__init__(
            data.park_info_coordinator,
            description=OPENING_HOURS_CALENDAR_DESCRIPTION,
            unique_id="opening_hours",
        )

    def _get_events(self) -> list[CalendarEvent]:
        """Return all opening intervals from the current park schedule."""
        return build_opening_hours_events(
            self.coordinator.data["OpeningHours"],
            language=self.hass.config.language,
        )
