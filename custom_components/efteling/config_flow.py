"""Adds config flow for Efteling."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries

from .const import DOMAIN, NAME


class EftelingFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Efteling."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        # When submit is pressed
        if user_input is not None:
            return self.async_create_entry(
                title=NAME,
                data={},
            )

        # Show the form initially
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
        )
