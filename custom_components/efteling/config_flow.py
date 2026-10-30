"""Adds config flow for Efteling."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import probatio as vol
else:
    import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.util import dt as dt_util

from custom_components.efteling.api import (
    EftelingApiClient,
    EftelingApiClientCommunicationError,
    EftelingApiClientError,
)
from custom_components.efteling.const import (
    CONF_LANGUAGE,
    DOMAIN,
    NAME,
    PARK_TIME_ZONE,
)


class EftelingFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Efteling."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        errors: dict[str, str] = {}
        default_language = "nl"

        if user_input is not None:
            default_language = str(user_input.get(CONF_LANGUAGE, "nl"))
            error = await self._async_validate_input(user_input)
            if error is None:
                return self.async_create_entry(title=NAME, data=user_input)
            errors["base"] = error

        return self._show_language_form(
            step_id="user",
            default_language=default_language,
            errors=errors,
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle reconfiguration of an existing entry."""
        entry = self._get_reconfigure_entry()
        default_language = str(entry.data.get(CONF_LANGUAGE, "nl"))
        errors: dict[str, str] = {}

        if user_input is not None:
            default_language = str(user_input.get(CONF_LANGUAGE, "nl"))
            error = await self._async_validate_input(user_input)
            if error is None:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=user_input,
                )
            errors["base"] = error

        return self._show_language_form(
            step_id="reconfigure",
            default_language=default_language,
            errors=errors,
        )

    async def _async_validate_input(
        self,
        user_input: dict[str, Any],
    ) -> str | None:
        """Check that all required endpoints return valid responses."""
        client = EftelingApiClient(
            session=async_get_clientsession(self.hass),
            language=str(user_input.get(CONF_LANGUAGE, "nl")),
        )
        now = dt_util.now(PARK_TIME_ZONE)

        try:
            await asyncio.gather(
                client.async_get_poi_list(),
                client.async_get_wait_times(),
                client.async_get_park_info(now.year, now.month),
            )
        except EftelingApiClientCommunicationError:
            return "cannot_connect"
        except EftelingApiClientError:
            return "invalid_response"

        return None

    def _show_language_form(
        self,
        *,
        step_id: str,
        default_language: str = "nl",
        errors: dict[str, str],
    ) -> config_entries.ConfigFlowResult:
        """Show the language selection form."""
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_LANGUAGE,
                    default=default_language,
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=["nl", "en"],
                        mode=SelectSelectorMode.DROPDOWN,
                        translation_key="language",
                    )
                )
            }
        )

        return self.async_show_form(
            step_id=step_id,
            data_schema=data_schema,
            errors=errors,
        )
