"""Attraction maintenance calendar."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.calendar import CalendarEntityDescription, CalendarEvent

from custom_components.efteling_park.coordinator import EftelingParkInfoCoordinator

from .calendar_entity import (
    EftelingCalendarEntity,
    create_date_range_event,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from custom_components.efteling_park.data import EftelingData
    from custom_components.efteling_park.models import Maintenance

MAINTENANCE_CALENDAR_DESCRIPTION = CalendarEntityDescription(
    key="maintenance",
    translation_key="maintenance",
)


def build_maintenance_calendar_events(
    maintenance_items: Sequence[Maintenance],
) -> list[CalendarEvent]:
    """Build all-day events for attraction maintenance periods."""
    events: list[CalendarEvent] = []

    for index, item in enumerate(maintenance_items):
        name = item.get("Name")
        if not name:
            continue

        event = create_date_range_event(
            date_range=(item["DateFrom"], item["DateTo"]),
            summary=name,
            description=None,
            uid=f"maintenance-{index}",
            end_inclusive=False,
        )
        if event is not None:
            events.append(event)

    return events


class EftelingMaintenanceCalendar(EftelingCalendarEntity[EftelingParkInfoCoordinator]):
    """Calendar containing attraction maintenance periods."""

    def __init__(self, data: EftelingData) -> None:
        """Initialize the maintenance calendar."""
        super().__init__(
            data.park_info_coordinator,
            description=MAINTENANCE_CALENDAR_DESCRIPTION,
            unique_id="maintenance",
        )

    def _get_events(self) -> list[CalendarEvent]:
        """Return maintenance periods from the current park schedule."""
        return build_maintenance_calendar_events(self.coordinator.data["Maintenance"])
