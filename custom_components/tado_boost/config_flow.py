from __future__ import annotations

import logging
from homeassistant import config_entries
from homeassistant.helpers import config_entry_oauth2_flow
from .const import DOMAIN, OAUTH2_AUTHORIZE, OAUTH2_TOKEN, OAUTH2_SCOPES

_LOGGER = logging.getLogger(__name__)

class TadoOAuth2FlowHandler(config_entry_oauth2_flow.OAuth2FlowHandler, domain=DOMAIN):
    """OAuth2 config flow for Tado Boost using Home Assistant OAuth helper."""
    DOMAIN = DOMAIN
    OAUTH2_AUTHORIZE = OAUTH2_AUTHORIZE
    OAUTH2_TOKEN = OAUTH2_TOKEN
    OAUTH2_SCOPES = OAUTH2_SCOPES

    async def async_step_user(self, user_input=None):
        # Delegate to the helper which starts the authorize flow
        return await super().async_step_user()

    async def async_step_reauth(self, data):
        # Start the reauth (will prompt user to re-login)
        self._reauth_entry = data
        return await super().async_step_reauth(data)
