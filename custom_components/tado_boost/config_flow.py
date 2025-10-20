import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

# IMPORTANT: Ensure this imports TadoBoostApi, not TadoApi
from .api import TadoBoostApi
from .const import CONF_REFRESH_TOKEN, DOMAIN

_LOGGER = logging.getLogger(__name__)


class TadoBoostFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tado Boost, inspired by tado-assist."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow handler."""
        self.api: TadoBoostApi | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step. This will start the device activation flow."""
        if not self.api:
            # Pass entry=None for the initial setup, as there's no entry yet
            self.api = TadoBoostApi(self.hass, entry=None)

        try:
            status = await self.api.async_initialize()
            if status == "COMPLETED":
                return await self.async_step_finish()
            if status in ["NOT_STARTED", "PENDING"]:
                return await self.async_step_activation()
            
            _LOGGER.error("Unknown Tado activation status: %s", status)
            return self.async_abort(reason="cannot_connect")

        except Exception as e:
            _LOGGER.exception("Error during Tado initialization: %s", e)
            return self.async_abort(reason="cannot_connect")

    async def async_step_activation(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Show the activation link and wait for the user to submit."""
        assert self.api is not None

        if user_input is not None:
            # User has clicked submit, now we wait for activation
            try:
                success = await self.api.async_activate_device()
                if success:
                    return await self.async_step_finish()
                # If not successful, we show the form again, maybe with an error
                return self.async_show_form(
                    step_id="activation",
                    description_placeholders={"url": self.api.auth_url, "code": self.api.user_code},
                    errors={"base": "activation_failed"},
                    data_schema=vol.Schema({}),
                )
            except Exception as e:
                _LOGGER.exception("Error during Tado device activation: %s", e)
                return self.async_abort(reason="cannot_connect")

        # Show the form with the URL and code for the first time
        _LOGGER.debug("Displaying activation form with URL: %s and Code: %s", self.api.auth_url, self.api.user_code)
        return self.async_show_form(
            step_id="activation",
            description_placeholders={"url": self.api.auth_url, "code": self.api.user_code},
            data_schema=vol.Schema({}),
        )

    async def async_step_finish(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Finish the setup after successful authentication."""
        assert self.api is not None

        # We need to get the home info to set a unique ID
        try:
            # Use the _run method of TadoBoostApi to execute PyTado functions
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