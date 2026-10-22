"""Adds config flow for Efteling."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_LANGUAGE, DOMAIN, NAME


class EftelingFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Efteling."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if user_input is not None:
            return self.async_create_entry(
                title=NAME,
                data=user_input,
            )

        return await self._show_language_form("user")

    async def async_step_reconfigure(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle reconfiguration of an existing entry."""
        if user_input is not None:
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(),
                data_updates=user_input,
            )

        entry = self._get_reconfigure_entry()

        return await self._show_language_form(
            "reconfigure",
            default_language=entry.data.get(CONF_LANGUAGE, "nl"),
        )

    async def _show_language_form(
        self,
        step_id: str,
        default_language: str = "nl",
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
            data_schema=data_schema,  # type: ignore[reportArgumentType]  # HA's stub conflicts with voluptuous config flow schemas.
        )
