"""Calendar for Winter Efteling and business events."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.calendar import CalendarEntityDescription, CalendarEvent

from custom_components.efteling_park.coordinator import EftelingParkInfoCoordinator

from .calendar_entity import (
    EftelingCalendarEntity,
    create_date_range_event,
    plain_text,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from custom_components.efteling_park.data import EftelingData
    from custom_components.efteling_park.models import Event

EVENTS_CALENDAR_DESCRIPTION = CalendarEntityDescription(
    key="events",
    translation_key="events",
)


def build_events_calendar_events(
    source_events: Sequence[Event],
    *,
    language: str,
) -> list[CalendarEvent]:
    """Build all-day events for Winter Efteling and business events."""
    events: list[CalendarEvent] = []
    is_dutch = language.lower().startswith("nl")

    for index, item in enumerate(source_events):
        event_type = item["Type"]
        if event_type not in {"winter", "business"}:
            continue

        fallback_name = (
            "Winter Efteling"
            if event_type == "winter"
            else "Bedrijfsevenement"
            if is_dutch
            else "Business event"
        )
        details = plain_text(item.get("Description"))
        event = create_date_range_event(
            date_range=(item["DateFrom"], item["DateTo"]),
            summary=item.get("Name") or fallback_name,
            description=details,
            uid=f"efteling-event-{event_type}-{index}",
            end_inclusive=True,
        )
        if event is not None:
            events.append(event)

    return events


class EftelingEventsCalendar(EftelingCalendarEntity[EftelingParkInfoCoordinator]):
    """Calendar containing Winter Efteling and business-event dates."""

    def __init__(self, data: EftelingData) -> None:
        """Initialize the combined events calendar."""
        super().__init__(
            data.park_info_coordinator,
            description=EVENTS_CALENDAR_DESCRIPTION,
            unique_id="events",
        )

    def _get_events(self) -> list[CalendarEvent]:
        """Return Winter Efteling and business events from the park schedule."""
        return build_events_calendar_events(
            self.coordinator.data["Events"],
            language=self.hass.config.language,
        )
