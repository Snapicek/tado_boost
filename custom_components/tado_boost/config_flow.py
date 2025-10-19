from __future__ import annotations

import logging
from typing import Any

from PyTado.interface import Tado
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN


class TadoOAuth2FlowHandler(config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Tado Boost OAuth2 flow handler that integrates with Application Credentials."""

    DOMAIN = DOMAIN
    VERSION = 1

    @property
    def logger(self) -> logging.Logger:
        """Return the logger."""
        return logging.getLogger(__name__)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle a flow initiated by the user."""
        # This will start the OAuth2 flow managed by Home Assistant, which will
        # use the credentials stored in the Application Credentials system.
        return await self.async_step_pick_implementation(
            user_input=user_input,
        )

    async def async_oauth_create_entry(self, data: dict) -> FlowResult:
        """Create an entry for the flow, or update existing if reauth."""
        tado = Tado(token=data["token"])
        try:
            tado_me = await self.hass.async_add_executor_job(tado.get_me)
        except Exception as e:
            self.logger.error("Failed to get Tado account info: %s", e)
            return self.async_abort(reason="cannot_connect")

        if not tado_me.get("homes"):
            self.logger.error("No homes found in Tado account")
            return self.async_abort(reason="no_homes")

        # Use the first home's ID as the unique ID
        home = tado_me["homes"][0]
        unique_id = str(home["id"])
        name = home["name"]

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates=data)

        self.logger.info("Successfully created Tado Boost entry for home '%s'", name)
        return self.async_create_entry(title=name, data=data)
