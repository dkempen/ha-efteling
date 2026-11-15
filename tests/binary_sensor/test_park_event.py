"""Tests for Efteling park event binary sensors."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from custom_components.efteling_park.sensor import park_snapshot

if TYPE_CHECKING:
    from collections.abc import Callable

    import pytest
    from homeassistant.core import HomeAssistant, State
    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant.common import MockConfigEntry


async def test_event_sensors_expose_current_and_all_event_attributes(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    entity_registry_entry: Callable[[MockConfigEntry, str], er.RegistryEntry],
    entity_state: Callable[[str], State],
) -> None:
    """Expose normalized event attributes and current-day binary states."""
    monkeypatch.setattr(
        park_snapshot.dt_util,
        "now",
        lambda _tz=None: datetime(
            2026, 10, 23, 12, 0, tzinfo=ZoneInfo("Europe/Amsterdam")
        ),
    )
    loaded_entry.runtime_data.park_info_coordinator.async_set_updated_data(
        {
            "OpeningHours": [{"Date": "2026-10-23", "OpeningHours": []}],
            "Maintenance": [],
            "Events": [
                {
                    "DateFrom": "2026-10-23",
                    "DateTo": "2026-10-23",
                    "Type": "winter",
                    "Name": "Winter",
                },
                {
                    "DateFrom": "2026-10-23",
                    "DateTo": "2026-10-23",
                    "Type": "business",
                    "Name": "(Bedrijfs)evenement",
                },
                {
                    "DateFrom": "2026-10-24",
                    "DateTo": "2026-10-25",
                    "Type": "winter",
                    "Name": "Future",
                },
            ],
        }
    )
    await hass.async_block_till_done()

    winter = entity_registry_entry(loaded_entry, "park_winter_efteling")
    assert entity_state(winter.entity_id).state == "on"
    winter_state = entity_state(winter.entity_id)
    assert winter_state.attributes["current_winter_event"]["name"] == "Winter"
    assert len(winter_state.attributes["winter_events"]) == 2

    business = entity_registry_entry(loaded_entry, "park_business_event")
    assert entity_state(business.entity_id).state == "on"
    business_state = entity_state(business.entity_id)
    assert (
        business_state.attributes["business_events_today"][0]["name"]
        == "(Bedrijfs)evenement"
    )
