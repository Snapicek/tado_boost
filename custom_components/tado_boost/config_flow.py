from __future__ import annotations

import logging
import asyncio
from collections.abc import Mapping
from typing import Any

# Lazy/safe imports for optional dependencies
HAS_PYTADO = False
HAS_YARL = False
try:
    from yarl import URL
    HAS_YARL = True
except Exception:
    URL = None  # type: ignore

try:
    from PyTado.interface import Tado
    from PyTado.exceptions import TadoException
    from PyTado.http import DeviceActivationStatus
    HAS_PYTADO = True
except Exception:
    # These names will be referenced only if HAS_PYTADO is True
    Tado = None  # type: ignore
    TadoException = Exception  # type: ignore
    DeviceActivationStatus = None  # type: ignore

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlow

from .const import DOMAIN, CONF_REFRESH_TOKEN

_LOGGER = logging.getLogger(__name__)

# Timeout for device activation (seconds)
DEVICE_ACTIVATION_TIMEOUT = 300


class TadoOAuth2FlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for Tado Boost using device activation (PyTado)."""

    VERSION = 1

    def __init__(self) -> None:
        super().__init__()
        self.login_task: asyncio.Task | None = None
        self.refresh_token: str | None = None
        self.tado: 'Tado' | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigEntry | dict:
        """Start device activation login flow.

        This will show a progress step where the user is instructed to visit
        the displayed URL and enter the code. The helper will poll for device
        activation and obtain a refresh token which is stored in the config entry.
        """
        if not HAS_PYTADO:
            _LOGGER.error("PyTado library is not available. Install python-tado to use this integration.")
            return self.async_abort(reason="cannot_connect")

        if not HAS_YARL:
            _LOGGER.error("yarl library is not available. Install yarl to use the config flow.")
            return self.async_abort(reason="cannot_connect")

        # Ensure we have a Tado instance
        if self.tado is None:
            _LOGGER.debug("Initiating device activation")
            try:
                # Create Tado instance in executor because it may perform blocking network I/O
                self.tado = await self.hass.async_add_executor_job(Tado)
            except TadoException:
                _LOGGER.exception("Error while initiating Tado")
                return self.async_abort(reason="cannot_connect")
            except Exception:
                _LOGGER.exception("Unexpected error while initiating Tado")
                return self.async_abort(reason="cannot_connect")
            assert self.tado is not None

        # Get device verification URL in executor as it may perform network/blocking ops
        try:
            tado_device_url = await self.hass.async_add_executor_job(
                self.tado.device_verification_url
            )
        except Exception:
            _LOGGER.exception("Failed to get device verification URL")
            return self.async_abort(reason="cannot_connect")

        _LOGGER.debug("Device verification URL obtained: %s", tado_device_url)
        user_code = URL(tado_device_url).query.get("user_code")
        _LOGGER.debug("Device activation user code: %s", user_code)

        async def _wait_for_login() -> None:
            assert self.tado is not None
            _LOGGER.debug("Waiting for device activation (task started)")
            try:
                # device_activation blocks and should run in executor
                # wrap in asyncio.wait_for to avoid indefinite blocking
                await asyncio.wait_for(
                    self.hass.async_add_executor_job(self.tado.device_activation),
                    timeout=DEVICE_ACTIVATION_TIMEOUT,
                )
            except asyncio.TimeoutError:
                _LOGGER.warning("Device activation timed out after %s seconds", DEVICE_ACTIVATION_TIMEOUT)
                # propagate timeout so caller can show a friendly error
                raise
            except Exception as ex:  # pragma: no cover - propagate for logging
                _LOGGER.exception("Error while waiting for device activation: %s", ex)
                raise

            status = self.tado.device_activation_status()
            _LOGGER.debug("Device activation status after wait: %s", status)
            if (
                status
                is not DeviceActivationStatus.COMPLETED
            ):
                raise Exception("Device activation not completed")

        _LOGGER.debug("Checking login task")
        if self.login_task is None:
            _LOGGER.debug("Creating task for device activation")
            self.login_task = self.hass.async_create_task(_wait_for_login())
        else:
            _LOGGER.debug("Re-using existing login task: done=%s, cancelled=%s", getattr(self.login_task, "done", lambda: False)(), getattr(self.login_task, "cancelled", lambda: False)())

        if self.login_task.done():
            _LOGGER.debug("Login task is done, finalizing login")
            if self.login_task.exception():
                _LOGGER.exception("Login task finished with exception: %s", self.login_task.exception())
                exc = self.login_task.exception()
                # If it was a TimeoutError, give a specific user-friendly reason
                if isinstance(exc, asyncio.TimeoutError):
                    return self.async_abort(reason="activation_timeout")
                return self.async_abort(reason="cannot_connect")

            _LOGGER.debug("Login task completed successfully, fetching refresh token")
            # Obtain refresh token and create entry
            try:
                self.refresh_token = await self.hass.async_add_executor_job(
                    self.tado.get_refresh_token
                )
            except Exception:
                _LOGGER.exception("Failed to get refresh token from Tado")
                return self.async_abort(reason="cannot_connect")

            # Get me to find home id/name
            try:
                tado_me = await self.hass.async_add_executor_job(self.tado.get_me)
            except Exception:
                _LOGGER.exception("Failed to fetch Tado account info")
                return self.async_abort(reason="cannot_connect")

            if "homes" not in tado_me or len(tado_me["homes"]) == 0:
                return self.async_abort(reason="no_homes")

            home = tado_me["homes"][0]
            unique_id = str(home["id"])
            name = home["name"]

            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=name,
                data={CONF_REFRESH_TOKEN: self.refresh_token},
            )

        # Show form with activation link
        return self.async_show_form(
            step_id="user",
            description_placeholders={
                "url": tado_device_url,
                "code": user_code,
            },
        )

    async def async_step_reauth(self, data: Mapping[str, Any]) -> config_entries.ConfigEntry | dict:
        """Handle reauth by starting the device activation again."""
        self._reauth_entry = data
        # Reset state so we start a fresh activation
        self.login_task = None
        self.tado = None
        return await self.async_step_user()
