from __future__ import annotations

import logging
from typing import Any

from PyTado.interface import Tado
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class TadoOAuth2FlowHandler(config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Tado Boost OAuth2 flow handler."""

    DOMAIN = DOMAIN
    VERSION = 1

    @property
    def logger(self) -> logging.Logger:
        """Return the logger."""
        return _LOGGER

    async def async_oauth_create_entry(self, data: dict) -> dict:
        """Create an entry for the flow, or update existing if reauth."""
        
        # Create a Tado instance to get account info
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

    @staticmethod
    async def async_get_oauth_scopes(config_entry: ConfigEntry | None) -> list[str]:
        """Return the scopes required for the integration."""
        return ["home.user"]
