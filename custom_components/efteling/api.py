"""Sample API Client."""

from __future__ import annotations

import socket
from typing import TYPE_CHECKING, Any

import aiohttp
import async_timeout

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


class EftelingApiClientAuthenticationError(
    EftelingApiClientError,
):
    """Exception to indicate an authentication error."""


def _verify_response_or_raise(response: aiohttp.ClientResponse) -> None:
    """Verify that the response is valid."""
    if response.status in (401, 403):
        msg = "Invalid credentials"
        raise EftelingApiClientAuthenticationError(msg)
    response.raise_for_status()


class EftelingApiClient:
    """API client for Efteling POI and wait times."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize."""
        self._session = session

    async def async_get_poi_list(self) -> list[Poi]:
        """Return POI data (points of interest, for example attractions)."""
        response: PoiResponse = await self._api_wrapper(
            method="get", url=POINTS_OF_INTEREST_URL, headers=APP_HEADERS
        )
        return [poi["fields"] for poi in response["hits"]["hit"]]

    async def async_get_wait_times(self) -> list[AttractionInfo]:
        """Return wait times data."""
        response: WaitTimesResponse = await self._api_wrapper(
            method="get", url=WAIT_TIMES_URL, headers=APP_HEADERS
        )
        return response["AttractionInfo"]

    async def _api_wrapper(
        self,
        method: str,
        url: str,
        data: dict | None = None,
        headers: dict | None = None,
    ) -> Any:
        """Get information from the API."""
        try:
            async with async_timeout.timeout(10):
                response = await self._session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=data,
                )
                _verify_response_or_raise(response)
                return await response.json()

        except TimeoutError as exception:
            msg = f"Timeout error fetching information - {exception}"
            raise EftelingApiClientCommunicationError(msg) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            msg = f"Error fetching information - {exception}"
            raise EftelingApiClientCommunicationError(msg) from exception
        except Exception as exception:
            msg = f"Something really wrong happened! - {exception}"
            raise EftelingApiClientError(msg) from exception
