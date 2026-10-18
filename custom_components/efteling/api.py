"""Sample API Client."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, cast

import aiohttp

from custom_components.efteling.const import (
    APP_HEADERS,
    POINTS_OF_INTEREST_URL,
    WAIT_TIMES_URL,
)

if TYPE_CHECKING:
    from custom_components.efteling.models import (
        AttractionInfo,
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


def _verify_response_or_raise(response: aiohttp.ClientResponse) -> None:
    """Verify that the response is valid."""
    response.raise_for_status()


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

    async def _api_wrapper(
        self,
        method: str,
        url: str,
        data: dict | None = None,
        headers: dict | None = None,
    ) -> PoiResponse | WaitTimesResponse:
        """Get information from the API."""
        try:
            async with asyncio.timeout(10):
                async with self._session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=data,
                ) as response:
                    _verify_response_or_raise(response)
                    return cast(
                        "PoiResponse | WaitTimesResponse", await response.json()
                    )

        except TimeoutError as exception:
            msg = f"Timeout error fetching information - {exception}"
            raise EftelingApiClientCommunicationError(msg) from exception
        except (aiohttp.ClientError, json.JSONDecodeError) as exception:
            msg = f"Error fetching information - {exception}"
            raise EftelingApiClientCommunicationError(msg) from exception
