"""API Client for Efteling."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any, cast

import aiohttp

if TYPE_CHECKING:
    import probatio as vol
else:
    import voluptuous as vol

from custom_components.efteling.const import (
    APP_HEADERS,
    PARK_INFO_URL,
    POINTS_OF_INTEREST_URL,
    WAIT_TIMES_URL,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from custom_components.efteling.models import AttractionInfo, ParkInfoResponse, Poi


_SHOW_TIME_SCHEMA = vol.Schema(
    {
        vol.Required("StartDateTime"): str,
        vol.Optional("ShowDateTime"): vol.Any(str, None),
        vol.Optional("EndDateTime"): vol.Any(str, None),
        vol.Optional("Duration"): vol.Any(int, None),
        vol.Optional("Edition"): vol.Any(str, None),
    },
    extra=vol.ALLOW_EXTRA,
)

_POI_FIELDS_SCHEMA = vol.Schema(
    {
        vol.Required("id"): str,
        vol.Required("name"): str,
        vol.Required("category"): str,
        vol.Optional("alternateid"): vol.Any(str, None),
    },
    extra=vol.ALLOW_EXTRA,
)

_POI_HIT_SCHEMA = vol.Schema(
    {vol.Required("fields"): _POI_FIELDS_SCHEMA},
    extra=vol.ALLOW_EXTRA,
)

_POI_HITS_SCHEMA = vol.Schema(
    {vol.Required("hit"): [_POI_HIT_SCHEMA]},
    extra=vol.ALLOW_EXTRA,
)

_POI_RESPONSE_SCHEMA = vol.Schema(
    {vol.Required("hits"): _POI_HITS_SCHEMA},
    extra=vol.ALLOW_EXTRA,
)

_WAIT_TIME_RECORD_SCHEMA = vol.Schema(
    {
        vol.Required("Id"): str,
        vol.Required("Name"): str,
        vol.Required("State"): str,
        vol.Optional("Type"): vol.Any(str, None),
        vol.Optional("Empire"): vol.Any(str, None),
        vol.Optional("WaitingTime"): vol.Any(int, None),
        vol.Optional("ShowTimes"): vol.Any([_SHOW_TIME_SCHEMA], None),
        vol.Optional("PastShowTimes"): vol.Any([_SHOW_TIME_SCHEMA], None),
    },
    extra=vol.ALLOW_EXTRA,
)

_WAIT_TIME_RESPONSE_SCHEMA = vol.Schema(
    {vol.Required("AttractionInfo"): [_WAIT_TIME_RECORD_SCHEMA]},
    extra=vol.ALLOW_EXTRA,
)

_OPENING_INTERVAL_SCHEMA = vol.Schema(
    {
        vol.Optional("Open"): vol.Any(str, None),
        vol.Optional("Close"): vol.Any(str, None),
    },
    extra=vol.ALLOW_EXTRA,
)

_OPENING_DAY_SCHEMA = vol.Schema(
    {
        vol.Required("Date"): str,
        vol.Optional("OpeningHours"): vol.Any([_OPENING_INTERVAL_SCHEMA], None),
        vol.Optional("Crowded"): vol.Any(int, None),
        vol.Optional("Crowdedness"): vol.Any(int, None),
    },
    extra=vol.ALLOW_EXTRA,
)

_MAINTENANCE_SCHEMA = vol.Schema(
    {
        vol.Required("DateFrom"): str,
        vol.Required("DateTo"): str,
    },
    extra=vol.ALLOW_EXTRA,
)

_EVENT_SCHEMA = vol.Schema(
    {
        vol.Required("DateFrom"): str,
        vol.Required("DateTo"): str,
        vol.Required("Type"): str,
    },
    extra=vol.ALLOW_EXTRA,
)

_PARK_INFO_RESPONSE_SCHEMA = vol.Schema(
    {
        vol.Optional("OpeningHours", default=[]): vol.Any([_OPENING_DAY_SCHEMA], None),
        vol.Optional("Maintenance", default=[]): vol.Any([_MAINTENANCE_SCHEMA], None),
        vol.Optional("Events", default=[]): vol.Any([_EVENT_SCHEMA], None),
    },
    extra=vol.ALLOW_EXTRA,
)


class EftelingApiClientError(Exception):
    """Exception to indicate a general API error."""


class EftelingApiClientCommunicationError(
    EftelingApiClientError,
):
    """Exception to indicate a communication error."""


def _verify_response_or_raise(response: aiohttp.ClientResponse) -> None:
    """Verify that the response is valid."""
    response.raise_for_status()


def _validate_response(
    response: dict[str, Any],
    schema: Callable[[dict[str, Any]], Any],
    description: str,
) -> dict[str, Any]:
    """Validate an API response."""
    try:
        return cast("dict[str, Any]", schema(response))
    except vol.Invalid as exception:
        msg = f"Invalid {description} response: {exception}"
        raise EftelingApiClientError(msg) from exception


class EftelingApiClient:
    """API client for Efteling POI and wait times."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        language: str = "nl",
    ) -> None:
        """Initialize."""
        self._session = session
        self._language = language if language in ("nl", "en") else "nl"

    @property
    def headers(self) -> dict[str, str]:
        """Return headers for API requests."""
        return {
            **APP_HEADERS,
            "x-app-language": self._language,
            "accept-language": self._language,
        }

    async def async_get_poi_list(self) -> list[Poi]:
        """Return POI data (points of interest, for example attractions)."""
        response = await self._async_get_json(POINTS_OF_INTEREST_URL, self.headers)
        parsed = _validate_response(response, _POI_RESPONSE_SCHEMA, "POI")
        hits = cast("dict[str, object]", parsed["hits"])
        records = cast("list[dict[str, object]]", hits["hit"])
        return [cast("Poi", record["fields"]) for record in records]

    async def async_get_wait_times(self) -> list[AttractionInfo]:
        """Return wait times data."""
        response = await self._async_get_json(WAIT_TIMES_URL, self.headers)
        parsed = _validate_response(
            response,
            _WAIT_TIME_RESPONSE_SCHEMA,
            "wait-times",
        )
        return cast("list[AttractionInfo]", parsed["AttractionInfo"])

    async def async_get_park_info(self, year: int, month: int) -> ParkInfoResponse:
        """Return park schedules for the requested month."""
        response = await self._async_get_json(
            f"{PARK_INFO_URL}/{self._language}/{year}/{month:02d}",
            {**self.headers, "host": "www.efteling.com"},
        )
        parsed = _validate_response(
            response,
            _PARK_INFO_RESPONSE_SCHEMA,
            "park information",
        )

        for key in ("OpeningHours", "Maintenance", "Events"):
            if parsed.get(key) is None:
                parsed[key] = []

        return cast("ParkInfoResponse", parsed)

    async def _async_get_json(
        self, url: str, headers: dict[str, str]
    ) -> dict[str, object]:
        """Fetch a JSON object from an Efteling endpoint."""
        return await self._api_wrapper("get", url, headers=headers)

    async def _api_wrapper(
        self,
        method: str,
        url: str,
        data: dict | None = None,
        headers: dict | None = None,
    ) -> dict[str, object]:
        """Get information from the API."""
        try:
            async with asyncio.timeout(10):
                async with self._session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=data,
                ) as response:
                    if response.status in (401, 403):
                        msg = f"Efteling API access denied with HTTP {response.status}"
                        raise EftelingApiClientError(msg)
                    _verify_response_or_raise(response)
                    payload = await response.json()
                    if not isinstance(payload, dict):
                        msg = "Invalid API response: expected a JSON object"
                        raise EftelingApiClientError(msg)
                    return cast("dict[str, object]", payload)

        except TimeoutError as exception:
            msg = f"Timeout error fetching information - {exception}"
            raise EftelingApiClientCommunicationError(msg) from exception
        except (aiohttp.ClientError, json.JSONDecodeError) as exception:
            msg = f"Error fetching information - {exception}"
            raise EftelingApiClientCommunicationError(msg) from exception
