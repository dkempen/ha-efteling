"""Show performance calendar."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.components.calendar import CalendarEntityDescription, CalendarEvent
from homeassistant.core import callback

from custom_components.efteling_park.coordinator import EftelingWaitTimesCoordinator
from custom_components.efteling_park.show_utils import (
    parse_show_datetime,
    parse_show_duration,
)

from .calendar_entity import EftelingCalendarEntity

if TYPE_CHECKING:
    from custom_components.efteling_park.data import EftelingData
    from custom_components.efteling_park.models import AttractionInfo, Poi

SHOWS_CALENDAR_DESCRIPTION = CalendarEntityDescription(
    key="shows",
    translation_key="shows",
)


def build_show_calendar_events(
    wait_times: dict[str, AttractionInfo],
    pois: dict[str, Poi],
) -> list[CalendarEvent]:
    """Build timed calendar events for all POIs categorized as shows."""
    events: dict[tuple[str, str], CalendarEvent] = {}

    for show_id, show in wait_times.items():
        poi = pois.get(show_id)
        if poi is None or poi["category"] != "show":
            continue

        summary = poi.get("name") or show["Name"] or show_id

        for showtimes in (show.get("ShowTimes"), show.get("PastShowTimes")):
            if showtimes is None:
                continue

            for item in showtimes:
                start = parse_show_datetime(item.get("StartDateTime"))
                if start is None:
                    continue

                end = parse_show_datetime(item.get("EndDateTime"))
                duration = parse_show_duration(item.get("Duration"))
                if end is None and duration is not None:
                    end = start + timedelta(minutes=duration)

                if end is None or end <= start:
                    continue

                event = CalendarEvent(
                    start=start,
                    end=end,
                    summary=str(summary),
                    description=item.get("Edition") or "",
                    uid=f"show-{show_id}-{start.isoformat()}",
                )
                events[(show_id, start.isoformat())] = event

    return sorted(events.values(), key=lambda item: item.start_datetime_local)


class EftelingShowsCalendar(EftelingCalendarEntity[EftelingWaitTimesCoordinator]):
    """Calendar containing scheduled performances for all Efteling shows."""

    def __init__(self, data: EftelingData) -> None:
        """Initialize the shows calendar."""
        super().__init__(
            data.wait_times_coordinator,
            description=SHOWS_CALENDAR_DESCRIPTION,
            unique_id="shows",
        )
        self._data = data

    async def async_added_to_hass(self) -> None:
        """Listen for POI changes because they determine which entries are shows."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._data.poi_coordinator.async_add_listener(self._handle_poi_update)
        )

    @callback
    def _handle_poi_update(self) -> None:
        """Refresh the calendar when show POI metadata changes."""
        self.async_write_ha_state()

    def _get_events(self) -> list[CalendarEvent]:
        """Return all show performances from the live wait-times feed."""
        return build_show_calendar_events(
            self.coordinator.data,
            self._data.poi_coordinator.data,
        )
