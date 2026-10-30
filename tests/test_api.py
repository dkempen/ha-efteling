"""Tests for the Efteling API client."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.efteling.api import (
    _PARK_INFO_RESPONSE_SCHEMA,
    _POI_RESPONSE_SCHEMA,
    _WAIT_TIME_RESPONSE_SCHEMA,
    EftelingApiClient,
    EftelingApiClientCommunicationError,
    EftelingApiClientError,
    _validate_response,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractContextManager
    from typing import Any

    from custom_components.efteling.models import (
        ParkInfoResponse,
        PoiResponse,
        WaitTimesResponse,
    )


def _raises(
    exception_type: type[Exception],
    match: str | None = None,
) -> AbstractContextManager[Any]:
    """Return pytest's exception context with its intended context-manager type."""
    context = (
        pytest.raises(exception_type)
        if match is None
        else pytest.raises(exception_type, match=match)
    )
    return cast("AbstractContextManager[Any]", context)


def test_poi_schema_accepts_unknown_nested_fields() -> None:
    """Allow upstream additions at all levels of the POI response."""
    response = {
        "hits": {
            "hit": [
                {
                    "fields": {
                        "id": "python",
                        "name": "Python",
                        "category": "attraction",
                        "new_field": {"value": 1},
                    },
                    "hit_field": True,
                }
            ],
            "hits_field": True,
        },
        "response_field": True,
    }
    parsed = _validate_response(response, _POI_RESPONSE_SCHEMA, "POI")
    assert parsed["hits"]["hit"][0]["fields"]["new_field"] == {"value": 1}


def test_wait_time_schema_accepts_nested_fields_and_nulls() -> None:
    """Keep optional nulls and additional showtime fields valid."""
    response = {
        "AttractionInfo": [
            {
                "Id": "aquanura",
                "Name": "Aquanura",
                "State": "open",
                "Type": None,
                "WaitingTime": 0,
                "ShowTimes": [
                    {
                        "StartDateTime": "2026-10-23T20:00:00",
                        "EndDateTime": None,
                        "new_show_field": True,
                    }
                ],
                "new_record_field": "value",
            }
        ]
    }
    parsed = _validate_response(response, _WAIT_TIME_RESPONSE_SCHEMA, "wait-times")
    record = parsed["AttractionInfo"][0]
    assert record["new_record_field"] == "value"
    assert record["ShowTimes"][0]["new_show_field"] is True


def test_park_info_schema_accepts_nested_fields_and_nulls() -> None:
    """Allow API additions in schedule, maintenance, and event records."""
    response = {
        "OpeningHours": [
            {
                "Date": "2026-10-23",
                "NewDayField": 1.5,
                "OpeningHours": [
                    {"Open": "10:00", "Close": None, "new_interval": True}
                ],
            }
        ],
        "Maintenance": [
            {"DateFrom": "2026-10-23", "DateTo": "2026-10-24", "New": True}
        ],
        "Events": [
            {
                "DateFrom": "2026-10-23",
                "DateTo": "2026-10-23",
                "Type": "winter",
                "New": "field",
            }
        ],
    }
    parsed = _validate_response(
        response,
        _PARK_INFO_RESPONSE_SCHEMA,
        "park information",
    )
    assert parsed["OpeningHours"][0]["NewDayField"] == 1.5
    assert parsed["OpeningHours"][0]["OpeningHours"][0]["new_interval"] is True
    assert parsed["Maintenance"][0]["New"] is True
    assert parsed["Events"][0]["New"] == "field"


@pytest.mark.parametrize(
    ("response", "schema", "description"),
    [
        ({}, _POI_RESPONSE_SCHEMA, "POI"),
        ({"AttractionInfo": [{"Id": "one"}]}, _WAIT_TIME_RESPONSE_SCHEMA, "wait-times"),
        (
            {"Events": [{"DateFrom": "2026-10-23"}]},
            _PARK_INFO_RESPONSE_SCHEMA,
            "park information",
        ),
    ],
)
def test_schemas_reject_missing_required_fields(
    response: dict[str, object],
    schema: Callable[[dict[str, Any]], Any],
    description: str,
) -> None:
    """Reject malformed records despite allowing unknown fields."""
    with _raises(EftelingApiClientError, f"Invalid {description} response"):
        _validate_response(response, schema, description)


def test_api_client_falls_back_to_dutch_for_unknown_language() -> None:
    """Keep API language headers restricted to supported languages."""
    client = EftelingApiClient(MagicMock(), language="fr")
    assert client.headers["x-app-language"] == "nl"
    assert client.headers["accept-language"] == "nl"


@pytest.mark.asyncio
async def test_client_parses_real_api_responses(
    api_response_payloads: tuple[PoiResponse, WaitTimesResponse, ParkInfoResponse],
) -> None:
    """Parse the supplied response samples through the public client methods."""
    client = EftelingApiClient(MagicMock())
    with patch.object(
        client,
        "_async_get_json",
        new_callable=AsyncMock,
        side_effect=api_response_payloads,
    ):
        poi_records = await client.async_get_poi_list()
        wait_records = await client.async_get_wait_times()
        park_info = await client.async_get_park_info(2026, 11)

    poi_by_id = {poi["id"]: poi for poi in poi_records}
    assert poi_by_id["python"].get("alternateid") == "pythonsinglerider"

    wait_by_id = {record["Id"]: record for record in wait_records}
    assert wait_by_id["python"].get("WaitingTime") == 5
    assert "WaitingTime" not in wait_by_id["diorama"]
    show_times = wait_by_id["aquanura"].get("ShowTimes")
    assert show_times is not None
    assert show_times[0].get("Edition") == "Aquanura, met een zachte G"

    assert park_info["OpeningHours"][0]["Date"] == "2026-11-01"
    intervals = park_info["OpeningHours"][0].get("OpeningHours")
    assert intervals is not None
    assert intervals[0] == {
        "Open": "10:00",
        "Close": "20:00",
    }
    assert park_info["Maintenance"][0].get("State") is None
    assert park_info["Events"][0]["Type"] == "winter"


@pytest.mark.asyncio
async def test_get_poi_list_preserves_unknown_fields() -> None:
    """Return all validated POI fields, including additions from the API."""
    client = _client_for_response(
        payload={
            "hits": {
                "hit": [
                    {
                        "fields": {
                            "id": "python",
                            "name": "Python",
                            "category": "attraction",
                            "extra": "kept",
                        }
                    }
                ]
            }
        }
    )
    result = await client.async_get_poi_list()
    assert cast("dict[str, object]", result[0])["extra"] == "kept"


@pytest.mark.asyncio
async def test_get_wait_times_returns_validated_records() -> None:
    """Return records with optional fields after schema validation."""
    client = _client_for_response(
        payload={
            "AttractionInfo": [
                {"Id": "one", "Name": "One", "State": "closed", "extra": 1}
            ]
        }
    )
    result = await client.async_get_wait_times()
    assert cast("dict[str, object]", result[0])["extra"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [{}, {"OpeningHours": None, "Maintenance": None, "Events": None}],
)
async def test_get_park_info_normalizes_missing_lists(
    response: dict[str, object],
) -> None:
    """Normalize missing and explicit-null park information collections."""
    client = _client_for_response(payload=response)
    result = await client.async_get_park_info(2026, 10)
    assert result == {"OpeningHours": [], "Maintenance": [], "Events": []}


def _client_for_response(
    *,
    status: int = 200,
    payload: object | None = None,
    json_error: Exception | None = None,
    status_error: Exception | None = None,
) -> EftelingApiClient:
    """Create a client backed by an asynchronous mock response context."""
    response = MagicMock()
    response.status = status
    response.raise_for_status.side_effect = status_error
    response.json = AsyncMock(
        side_effect=json_error,
        return_value=payload,
    )
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=response)
    context.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.request.return_value = context
    return EftelingApiClient(session)


@pytest.mark.asyncio
async def test_park_info_fetches_json_object() -> None:
    """Fetch an object and normalize omitted park-information collections."""
    client = _client_for_response(payload={})
    result = await client.async_get_park_info(2026, 10)
    assert result == {"OpeningHours": [], "Maintenance": [], "Events": []}


@pytest.mark.asyncio
async def test_api_wrapper_rejects_non_object_json() -> None:
    """Treat a non-object response as an invalid API response."""
    client = _client_for_response(payload=[])
    with _raises(EftelingApiClientError, "expected a JSON object"):
        await client.async_get_park_info(2026, 10)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403])
async def test_api_wrapper_treats_access_denial_as_invalid_response(
    status: int,
) -> None:
    """Keep access denial distinct from transport failures."""
    client = _client_for_response(status=status)
    with _raises(EftelingApiClientError, f"HTTP {status}"):
        await client.async_get_park_info(2026, 10)


@pytest.mark.asyncio
async def test_api_wrapper_maps_http_errors_to_communication_error() -> None:
    """Map HTTP server failures to the communication error category."""
    error = aiohttp.ClientResponseError(
        request_info=MagicMock(),
        history=(),
        status=503,
    )
    client = _client_for_response(status_error=error)
    with _raises(EftelingApiClientCommunicationError):
        await client.async_get_park_info(2026, 10)


@pytest.mark.asyncio
async def test_api_wrapper_maps_malformed_json_to_communication_error() -> None:
    """Report malformed response JSON separately from schema validation."""
    error = json.JSONDecodeError("invalid", "", 0)
    client = _client_for_response(json_error=error)
    with _raises(EftelingApiClientCommunicationError):
        await client.async_get_park_info(2026, 10)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [TimeoutError, aiohttp.ClientConnectionError],
)
async def test_api_wrapper_maps_network_failures(
    error: type[Exception],
) -> None:
    """Map request timeouts and network errors to communication failures."""
    session = MagicMock()
    session.request.side_effect = error
    client = EftelingApiClient(session)
    with _raises(EftelingApiClientCommunicationError):
        await client.async_get_park_info(2026, 10)
