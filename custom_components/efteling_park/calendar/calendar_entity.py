"""Shared calendar entity and event helpers for Efteling."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from typing import TYPE_CHECKING, Any

from homeassistant.components.calendar import (
    CalendarEntity,
    CalendarEntityDescription,
    CalendarEvent,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from custom_components.efteling_park.const import PARK
from custom_components.efteling_park.entity import EftelingEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def parse_calendar_date(value: str | None) -> date | None:
    """Parse a date or an ISO date-time string into its calendar date."""
    if value is None:
        return None

    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def create_date_range_event(
    date_range: tuple[str, str],
    *,
    summary: str,
    description: str | None,
    uid: str,
    end_inclusive: bool,
) -> CalendarEvent | None:
    """Create an all-day event from an API date range."""
    date_from, date_to = date_range
    start = parse_calendar_date(date_from)
    end = parse_calendar_date(date_to)

    if start is None or end is None:
        return None

    if end_inclusive:
        end += timedelta(days=1)

    if end <= start:
        return None

    return CalendarEvent(
        start=start,
        end=end,
        summary=summary,
        description=description,
        uid=uid,
    )


class _PlainTextParser(HTMLParser):
    """Extract readable text from the HTML event descriptions."""

    def __init__(self) -> None:
        """Initialize the HTML parser."""
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        """Collect text nodes."""
        self.parts.append(data)


def plain_text(value: str | None) -> str | None:
    """Convert an optional HTML string into normalized plain text."""
    if not value:
        return None

    parser = _PlainTextParser()
    parser.feed(value)
    result = " ".join(" ".join(parser.parts).split())
    return result or None


class EftelingCalendarEntity[CoordinatorT: DataUpdateCoordinator[Any]](
    EftelingEntity[CoordinatorT], CalendarEntity
):
    """Base class for calendar entities on the Efteling park device."""

    def __init__(
        self,
        coordinator: CoordinatorT,
        *,
        description: CalendarEntityDescription,
        unique_id: str,
    ) -> None:
        """Initialize the calendar entity."""
        super().__init__(
            coordinator,
            device_key=PARK,
            device_translation_key="efteling_park",
        )
        self.entity_description = description
        self._attr_unique_id = unique_id

    def _get_events(self) -> list[CalendarEvent]:
        """Return all events currently available from the source coordinator."""
        raise NotImplementedError

    @property
    def event(self) -> CalendarEvent | None:
        """Return the current event or the next upcoming event."""
        now = dt_util.now()
        return next(
            (
                event
                for event in sorted(
                    self._get_events(),
                    key=lambda item: item.start_datetime_local,
                )
                if event.end_datetime_local > now
            ),
            None,
        )

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return events that overlap the requested time range."""
        del hass
        start = dt_util.as_local(start_date)
        end = dt_util.as_local(end_date)

        return [
            event
            for event in sorted(
                self._get_events(),
                key=lambda item: item.start_datetime_local,
            )
            if event.end_datetime_local > start and event.start_datetime_local < end
        ]
