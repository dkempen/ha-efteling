"""Config flow for Efteling."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

    import probatio as vol
else:
    import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.util import dt as dt_util

from custom_components.efteling_park.api import (
    EftelingApiClient,
    EftelingApiClientCommunicationError,
    EftelingApiClientError,
)
from custom_components.efteling_park.const import (
    CONF_CREATE_ATTRACTION_STATUS_SENSORS,
    CONF_LANGUAGE,
    DEFAULT_CREATE_ATTRACTION_STATUS_SENSORS,
    DEFAULT_LANGUAGE,
    DOMAIN,
    NAME,
    PARK_TIME_ZONE,
)


def _get_options_schema(
    options: Mapping[str, Any] | None = None,
    data: Mapping[str, Any] | None = None,
) -> vol.Schema:
    """Create the shared configuration and options schema."""
    current = {
        **(data or {}),
        **(options or {}),
    }

    return vol.Schema(
        {
            vol.Required(
                CONF_LANGUAGE,
                default=current.get(CONF_LANGUAGE, DEFAULT_LANGUAGE),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=["nl", "en"],
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key="language",
                )
            ),
            vol.Required(
                CONF_CREATE_ATTRACTION_STATUS_SENSORS,
                default=current.get(
                    CONF_CREATE_ATTRACTION_STATUS_SENSORS,
                    DEFAULT_CREATE_ATTRACTION_STATUS_SENSORS,
                ),
            ): BooleanSelector(),
        }
    )


class EftelingFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Efteling."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> EftelingOptionsFlowHandler:
        """Return the options flow handler."""
        del config_entry
        return EftelingOptionsFlowHandler()

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle initial integration setup."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        errors: dict[str, str] = {}

        if user_input is not None:
            error = await self._async_validate_input(user_input)

            if error is None:
                return self.async_create_entry(
                    title=NAME,
                    data={},
                    options=user_input,
                )

            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=_get_options_schema(options=user_input),
            errors=errors,
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle reconfiguration of an existing entry."""
        entry = self._get_reconfigure_entry()

        await self.async_set_unique_id(entry.unique_id)
        self._abort_if_unique_id_mismatch()

        errors: dict[str, str] = {}

        if user_input is not None:
            error = await self._async_validate_input(user_input)

            if error is None:
                return self.async_update_reload_and_abort(
                    entry,
                    options=user_input,
                    reason="reconfigure_successful",
                )

            errors["base"] = error

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_get_options_schema(
                options=user_input if user_input is not None else entry.options,
                data=entry.data,
            ),
            errors=errors,
        )

    async def _async_validate_input(
        self,
        user_input: dict[str, Any],
    ) -> str | None:
        """Check that all required endpoints return valid responses."""
        client = EftelingApiClient(
            session=async_get_clientsession(self.hass),
            language=str(user_input[CONF_LANGUAGE]),
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


class EftelingOptionsFlowHandler(config_entries.OptionsFlowWithReload):
    """Handle Efteling options."""

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Manage Efteling options."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data=user_input,
            )

        entry = self.config_entry

        return self.async_show_form(
            step_id="init",
            data_schema=_get_options_schema(
                options=entry.options,
                data=entry.data,
            ),
        )
