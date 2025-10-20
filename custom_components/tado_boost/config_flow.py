import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult, AbortFlow

from .api import TadoBoostApi
from .const import CONF_REFRESH_TOKEN, DOMAIN

_LOGGER = logging.getLogger(__name__)


class TadoBoostFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tado Boost."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow handler."""
        self.api: TadoBoostApi | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step, starting the device activation flow."""
        if not self.api:
            self.api = TadoBoostApi(self.hass, entry=None)

        try:
            status = await self.api.async_initialize()
            if status == "COMPLETED":
                return await self.async_step_finish()
            if status in ["NOT_STARTED", "PENDING"]:
                return await self.async_step_activation()
            
            _LOGGER.error("Unknown Tado activation status: %s", status)
            return self.async_abort(reason="cannot_connect")
        except AbortFlow:
            return self.async_abort(reason="already_configured")
        except Exception as e:
            _LOGGER.exception("Error during Tado initialization: %s", e)
            return self.async_abort(reason="cannot_connect")

    async def async_step_activation(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Show the activation link and wait for user submission."""
        assert self.api is not None

        if user_input is not None:
            try:
                success = await self.api.async_activate_device()
                if success:
                    return await self.async_step_finish()

                return self.async_show_form(
                    step_id="activation",
                    description_placeholders={"url": self.api.auth_url, "code": self.api.user_code},
                    errors={"base": "activation_failed"},
                    data_schema=vol.Schema({}),
                )
            except AbortFlow:
                return self.async_abort(reason="already_configured")
            except Exception as e:
                _LOGGER.exception("Error during Tado device activation: %s", e)
                return self.async_abort(reason="cannot_connect")

        return self.async_show_form(
            step_id="activation",
            description_placeholders={"url": self.api.auth_url, "code": self.api.user_code},
            data_schema=vol.Schema({}),
        )

    async def async_step_finish(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Finish the setup after successful authentication."""
        assert self.api is not None

        try:
            tado_me = await self.api._run(self.api._tado.get_me)
        except Exception as e:
            _LOGGER.exception("Failed to get Tado account info after login: %s", e)
            return self.async_abort(reason="cannot_connect")

        if not tado_me.get("homes"):
            return self.async_abort(reason="no_homes")

        home = tado_me["homes"][0]
        unique_id = str(home["id"])
        name = home["name"]

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=name,
            data={CONF_REFRESH_TOKEN: self.api.refresh_token},
        )
