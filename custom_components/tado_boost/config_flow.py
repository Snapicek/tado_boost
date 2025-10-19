from __future__ import annotations

import logging
from homeassistant import config_entries

# Try to import OAuth2 helper in a robust way; some HA variants may not expose it
# or it may raise at import time. We avoid letting import errors propagate and
# provide a clear fallback that aborts the flow with a helpful message.
try:
    from homeassistant.helpers import config_entry_oauth2_flow
    OAuthHelperAvailable = hasattr(config_entry_oauth2_flow, "OAuth2FlowHandler")
except Exception as exc:  # pragma: no cover - runtime environments may differ
    config_entry_oauth2_flow = None  # type: ignore[assignment]
    OAuthHelperAvailable = False
    # Log full exception so the runtime reason is visible in Home Assistant logs
    _temp_logger = logging.getLogger("custom_components.tado_boost.import")
    _temp_logger.exception("Failed importing Home Assistant OAuth2 helper: %s", exc)

from .const import DOMAIN, OAUTH2_AUTHORIZE, OAUTH2_TOKEN, OAUTH2_SCOPES

_LOGGER = logging.getLogger(__name__)

if OAuthHelperAvailable:
    _LOGGER.debug("OAuth2 helper detected: using Home Assistant OAuth2FlowHandler")

    class TadoOAuth2FlowHandler(config_entry_oauth2_flow.OAuth2FlowHandler):
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
else:
    _LOGGER.debug("OAuth2 helper NOT detected at import time; falling back to aborting flow")

    class TadoOAuth2FlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
        """Fallback ConfigFlow when OAuth helper is not available."""

        async def async_step_user(self, user_input=None):
            _LOGGER.error(
                "OAuth2 helper not available in this Home Assistant; "
                "this integration requires a Home Assistant version that provides "
                "the OAuth2 config flow helper. Please upgrade Home Assistant "
                "to a recent release (recommended >= 2021.6) and try again."
            )
            return self.async_abort(reason="oauth_not_supported")

        async def async_step_reauth(self, data):
            _LOGGER.error(
                "OAuth2 helper not available for reauth; aborting reauth flow"
            )
            return self.async_abort(reason="reauth_not_supported")
