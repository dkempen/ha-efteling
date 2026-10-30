"""Tests for the Efteling config flow."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    SOURCE_USER,
    ConfigEntryState,
)
from homeassistant.const import CONF_LANGUAGE
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.efteling.api import (
    EftelingApiClient,
    EftelingApiClientCommunicationError,
    EftelingApiClientError,
)
from custom_components.efteling.config_flow import EftelingFlowHandler
from custom_components.efteling.const import DOMAIN

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from homeassistant.core import HomeAssistant


@pytest.fixture
async def unload_reconfigured_entry(
    hass: HomeAssistant,
    api_responses: None,
) -> AsyncGenerator[None]:
    """Drain and unload entries reloaded by reconfiguration tests."""
    del api_responses
    yield
    await hass.async_block_till_done()
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("method_name", "error", "expected"),
    [
        (method_name, error, expected)
        for method_name in (
            "async_get_poi_list",
            "async_get_wait_times",
            "async_get_park_info",
        )
        for error, expected in (
            (EftelingApiClientCommunicationError, "cannot_connect"),
            (EftelingApiClientError, "invalid_response"),
        )
    ],
)
async def test_user_flow_reports_validation_errors(
    hass: HomeAssistant,
    api_responses: None,
    method_name: str,
    error: type[Exception],
    expected: str,
) -> None:
    """Recover from each endpoint error in the same setup flow."""
    del api_responses
    successful_response = {
        "async_get_poi_list": [],
        "async_get_wait_times": [],
        "async_get_park_info": {
            "OpeningHours": [],
            "Maintenance": [],
            "Events": [],
        },
    }[method_name]
    with patch.object(
        EftelingApiClient,
        method_name,
        new_callable=AsyncMock,
        side_effect=[
            error("validation failed"),
            successful_response,
            successful_response,
        ],
    ) as poi_mock:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        flow_id = result["flow_id"]
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={CONF_LANGUAGE: "nl"},
        )
        assert result.get("type") == FlowResultType.FORM
        assert result.get("errors") == {"base": expected}
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={CONF_LANGUAGE: "en"},
        )
    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert "result" in result
    assert result["result"].unique_id == DOMAIN
    assert result.get("data") == {CONF_LANGUAGE: "en"}
    assert poi_mock.await_count >= 2


async def test_user_flow_creates_entry_after_all_checks_pass(
    hass: HomeAssistant,
    api_responses: None,
) -> None:
    """Create an entry only after all three endpoint checks succeed."""
    del api_responses
    with (
        patch.object(
            EftelingApiClient,
            "async_get_poi_list",
            new_callable=AsyncMock,
            return_value=[],
        ) as poi_mock,
        patch.object(
            EftelingApiClient,
            "async_get_wait_times",
            new_callable=AsyncMock,
            return_value=[],
        ) as wait_times_mock,
        patch.object(
            EftelingApiClient,
            "async_get_park_info",
            new_callable=AsyncMock,
            return_value={"OpeningHours": [], "Maintenance": [], "Events": []},
        ) as park_info_mock,
    ):
        original_create_entry = EftelingFlowHandler.async_create_entry

        def assert_validation_calls_before_entry_creation(
            flow: EftelingFlowHandler,
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            poi_mock.assert_awaited_once()
            wait_times_mock.assert_awaited_once()
            park_info_mock.assert_awaited_once()
            return original_create_entry(flow, *args, **kwargs)

        with patch.object(
            EftelingFlowHandler,
            "async_create_entry",
            autospec=True,
            side_effect=assert_validation_calls_before_entry_creation,
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_USER},
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={CONF_LANGUAGE: "en"},
            )
    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert "result" in result
    assert result["result"].unique_id == DOMAIN
    assert result.get("data") == {CONF_LANGUAGE: "en"}


async def test_user_flow_prevents_duplicate_entry(
    hass: HomeAssistant,
    api_responses: None,
) -> None:
    """Abort a second setup flow for the same Efteling account."""
    del api_responses
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LANGUAGE: "nl"},
    )
    duplicate = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert duplicate.get("type") == FlowResultType.ABORT
    assert duplicate.get("reason") == "single_instance_allowed"


@pytest.mark.usefixtures("unload_reconfigured_entry")
async def test_reconfigure_flow_prefills_and_updates_language(
    hass: HomeAssistant,
    api_responses: None,
) -> None:
    """Preserve the current language and update it after endpoint validation."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Efteling",
        data={CONF_LANGUAGE: "nl"},
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)
    del api_responses
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )
    assert result.get("type") == FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LANGUAGE: "en"},
    )
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "reconfigure_successful"
    assert entry.data[CONF_LANGUAGE] == "en"


@pytest.mark.parametrize(
    ("method_name", "error", "expected"),
    [
        (method_name, error, expected)
        for method_name in (
            "async_get_poi_list",
            "async_get_wait_times",
            "async_get_park_info",
        )
        for error, expected in (
            (EftelingApiClientCommunicationError, "cannot_connect"),
            (EftelingApiClientError, "invalid_response"),
        )
    ],
)
@pytest.mark.usefixtures("unload_reconfigured_entry")
async def test_reconfigure_flow_reports_validation_errors(
    hass: HomeAssistant,
    api_responses: None,
    method_name: str,
    error: type[Exception],
    expected: str,
) -> None:
    """Recover from each endpoint error in the same reconfiguration flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Efteling",
        data={CONF_LANGUAGE: "nl"},
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)
    del api_responses
    successful_response = {
        "async_get_poi_list": [],
        "async_get_wait_times": [],
        "async_get_park_info": {
            "OpeningHours": [],
            "Maintenance": [],
            "Events": [],
        },
    }[method_name]
    with patch.object(
        EftelingApiClient,
        method_name,
        new_callable=AsyncMock,
        side_effect=[
            error("validation failed"),
            successful_response,
            successful_response,
        ],
    ) as endpoint_mock:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
        )
        flow_id = result["flow_id"]
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={CONF_LANGUAGE: "nl"},
        )
        assert result.get("type") == FlowResultType.FORM
        assert result.get("errors") == {"base": expected}
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={CONF_LANGUAGE: "en"},
        )
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "reconfigure_successful"
    assert entry.data[CONF_LANGUAGE] == "en"
    assert endpoint_mock.await_count == 3
