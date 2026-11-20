"""Set up Efteling calendar entities."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers import entity_registry as er

from .annual_passes import (
    ANNUAL_PASS_CLASSIC_CALENDAR_DESCRIPTION,
    ANNUAL_PASS_PLUS_CALENDAR_DESCRIPTION,
    ANNUAL_PASS_PREMIUM_CALENDAR_DESCRIPTION,
    EftelingAnnualPassClassicCalendar,
    EftelingAnnualPassPlusCalendar,
    EftelingAnnualPassPremiumCalendar,
)
from .events import EVENTS_CALENDAR_DESCRIPTION, EftelingEventsCalendar
from .maintenance import (
    MAINTENANCE_CALENDAR_DESCRIPTION,
    EftelingMaintenanceCalendar,
)
from .opening_hours import (
    OPENING_HOURS_CALENDAR_DESCRIPTION,
    EftelingOpeningHoursCalendar,
)
from .shows import SHOWS_CALENDAR_DESCRIPTION, EftelingShowsCalendar

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from custom_components.efteling_park.data import EftelingConfigEntry

PARALLEL_UPDATES = 0

CALENDAR_ENTITY_DESCRIPTIONS = (
    OPENING_HOURS_CALENDAR_DESCRIPTION,
    EVENTS_CALENDAR_DESCRIPTION,
    MAINTENANCE_CALENDAR_DESCRIPTION,
    SHOWS_CALENDAR_DESCRIPTION,
    ANNUAL_PASS_CLASSIC_CALENDAR_DESCRIPTION,
    ANNUAL_PASS_PLUS_CALENDAR_DESCRIPTION,
    ANNUAL_PASS_PREMIUM_CALENDAR_DESCRIPTION,
)


def _remove_replaced_event_calendars(
    hass: HomeAssistant,
    entry: EftelingConfigEntry,
) -> None:
    """Remove replaced event calendar entries from the entity registry."""
    registry = er.async_get(hass)
    replaced_unique_ids = {"park_winter_efteling", "park_business_events"}

    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.domain == "calendar" and entity.unique_id in replaced_unique_ids:
            registry.async_remove(entity.entity_id)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EftelingConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Efteling calendars."""
    _remove_replaced_event_calendars(hass, entry)
    data = entry.runtime_data
    async_add_entities(
        [
            EftelingOpeningHoursCalendar(data),
            EftelingEventsCalendar(data),
            EftelingMaintenanceCalendar(data),
            EftelingShowsCalendar(data),
            EftelingAnnualPassClassicCalendar(data),
            EftelingAnnualPassPlusCalendar(data),
            EftelingAnnualPassPremiumCalendar(data),
        ]
    )
