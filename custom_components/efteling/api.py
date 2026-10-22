"""Sample API Client."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, cast

import aiohttp

from custom_components.efteling.const import (
    APP_HEADERS,
    PARK_INFO_URL,
    POINTS_OF_INTEREST_URL,
    WAIT_TIMES_URL,
)

if TYPE_CHECKING:
    from custom_components.efteling.models import (
        AttractionInfo,
        ParkInfoResponse,
        Poi,
        PoiResponse,
        WaitTimesResponse,
    )


class EftelingApiClientError(Exception):
    """Exception to indicate a general API error."""


class EftelingApiClientCommunicationError(
    EftelingApiClientError,
):
    """Exception to indicate a communication error."""


class EftelingApiClientAuthenticationError(EftelingApiClientError):
    """Exception to indicate an authentication error."""


def _verify_response_or_raise(response: aiohttp.ClientResponse) -> None:
    """Verify that the response is valid."""
    response.raise_for_status()


def _raise_authentication_error(status: int) -> None:
    """Raise the integration authentication error for an unauthorized response."""
    msg = f"Authentication failed with HTTP {status}"
    raise EftelingApiClientAuthenticationError(msg)


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
        response = cast(
            "PoiResponse",
            await self._api_wrapper(
                method="get",
                url=POINTS_OF_INTEREST_URL,
                headers=self.headers,
            ),
        )
        return [poi["fields"] for poi in response["hits"]["hit"]]

    async def async_get_wait_times(self) -> list[AttractionInfo]:
        """Return wait times data."""
        response = cast(
            "WaitTimesResponse",
            await self._api_wrapper(
                method="get",
                url=WAIT_TIMES_URL,
                headers=self.headers,
            ),
        )
        return response["AttractionInfo"]

    async def async_get_park_info(self, year: int, month: int) -> ParkInfoResponse:
        """Return park schedules for the requested month."""
        response = await self._api_wrapper(
            method="get",
            url=f"{PARK_INFO_URL}/{self._language}/{year}/{month:02d}",
            headers={**self.headers, "host": "www.efteling.com"},
        )
        if not isinstance(response, dict):
            msg = "Invalid park information response: expected an object"
            raise EftelingApiClientError(msg)
        schedule_keys = ("OpeningHours", "Maintenance", "Events")
        if any(
            response.get(key) is not None and not isinstance(response.get(key), list)
            for key in schedule_keys
        ):
            msg = (
                "Invalid park information response: expected OpeningHours, "
                "Maintenance, and Events lists or null"
            )
            raise EftelingApiClientError(msg)
        response = {
            **response,
            **{key: response.get(key) or [] for key in schedule_keys},
        }
        required_fields = {
            "OpeningHours": ("Date",),
            "Maintenance": ("DateFrom", "DateTo"),
            "Events": ("DateFrom", "DateTo", "Type"),
        }
        for key, fields in required_fields.items():
            records = response[key]
            if not all(
                isinstance(record, dict)
                and all(isinstance(record.get(field), str) for field in fields)
                for record in records
            ):
                msg = f"Invalid park information response: malformed {key} record"
                raise EftelingApiClientError(msg)
        park_response = cast("ParkInfoResponse", response)
        for day in park_response["OpeningHours"]:
            intervals = day.get("OpeningHours", [])
            if intervals is None:
                continue
            if not isinstance(intervals, list) or any(
                not isinstance(interval, dict)
                or any(
                    interval.get(field) is not None
                    and not isinstance(interval.get(field), str)
                    for field in ("Open", "Close")
                )
                for interval in intervals
            ):
                msg = "Invalid park information response: malformed opening interval"
                raise EftelingApiClientError(msg)
        return park_response

    async def _api_wrapper(
        self,
        method: str,
        url: str,
        data: dict | None = None,
        headers: dict | None = None,
    ) -> PoiResponse | WaitTimesResponse | ParkInfoResponse:
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
                        _raise_authentication_error(response.status)
                    _verify_response_or_raise(response)
                    return cast(
                        "PoiResponse | WaitTimesResponse | ParkInfoResponse",
                        await response.json(),
                    )

        except TimeoutError as exception:
            msg = f"Timeout error fetching information - {exception}"
            raise EftelingApiClientCommunicationError(msg) from exception
        except EftelingApiClientAuthenticationError:
            raise
        except (aiohttp.ClientError, json.JSONDecodeError) as exception:
            msg = f"Error fetching information - {exception}"
            raise EftelingApiClientCommunicationError(msg) from exception
