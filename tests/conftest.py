"""Shared fixtures for Efteling tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import CONF_LANGUAGE

if TYPE_CHECKING:
    from collections.abc import Generator

    from homeassistant.core import HomeAssistant

    from custom_components.efteling.models import (
        ParkInfoResponse,
        PoiResponse,
        WaitTimesResponse,
    )
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.efteling.api import EftelingApiClient
from custom_components.efteling.const import DOMAIN


@pytest.fixture(autouse=True)
def enable_integration(enable_custom_integrations: None) -> None:
    """Enable loading the local custom integration in tests."""
    del enable_custom_integrations


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Return an Efteling config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Efteling",
        data={CONF_LANGUAGE: "nl"},
        unique_id=DOMAIN,
    )


@pytest.fixture
def api_response_payloads() -> tuple[PoiResponse, WaitTimesResponse, ParkInfoResponse]:
    """Load representative responses captured from the Efteling API."""
    responses_dir = Path(__file__).parent / "responses"
    poi = json.loads((responses_dir / "poi.json").read_text())
    wait_times = json.loads((responses_dir / "wait_times.json").read_text())
    park_info = json.loads((responses_dir / "park_info.json").read_text())
    return poi, wait_times, park_info


@pytest.fixture
def api_responses(
    api_response_payloads: tuple[PoiResponse, WaitTimesResponse, ParkInfoResponse],
) -> Generator[None]:
    """Return parsed API records for integration setup tests."""
    poi_response, wait_times_response, park_info = api_response_payloads
    poi = [record["fields"] for record in poi_response["hits"]["hit"]]
    wait_times = wait_times_response["AttractionInfo"]
    with (
        patch.object(
            EftelingApiClient,
            "async_get_poi_list",
            new_callable=AsyncMock,
            return_value=poi,
        ),
        patch.object(
            EftelingApiClient,
            "async_get_wait_times",
            new_callable=AsyncMock,
            return_value=wait_times,
        ),
        patch.object(
            EftelingApiClient,
            "async_get_park_info",
            new_callable=AsyncMock,
            return_value=park_info,
        ),
    ):
        yield


@pytest.fixture
async def loaded_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    api_responses: None,
) -> MockConfigEntry:
    """Set up the integration and return its loaded config entry."""
    del api_responses
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry
