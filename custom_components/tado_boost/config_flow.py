from __future__ import annotations

import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD

_LOGGER = logging.getLogger(__name__)

class TadoBoostConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            # validate credentials by attempting to authenticate using a temporary API client
            from .api import TadoApi, TadoApiError
            api = TadoApi(self.hass, user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
            try:
                await api.async_authenticate()
            except TadoApiError as err:
                _LOGGER.debug("Auth failed: %s", err)
                errors["base"] = "invalid_auth"
            else:
                return self.async_create_entry(title=user_input[CONF_USERNAME], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=errors,
        )

    async def async_step_reauth(self, data):
        # offer reauth confirm step
        self._reauth_entry = data
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        errors = {}
        if user_input is not None:
            from .api import TadoApi, TadoApiError
            username = self._reauth_entry.get(CONF_USERNAME)
            api = TadoApi(self.hass, username, user_input[CONF_PASSWORD])
            try:
                await api.async_authenticate()
            except TadoApiError:
                errors["base"] = "invalid_auth"
            else:
                # update existing entry
                entries = list(self._async_current_entries())
                if entries:
                    entry = entries[0]
                    self.hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_PASSWORD: user_input[CONF_PASSWORD]})
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )

