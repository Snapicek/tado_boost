from __future__ import annotations

import logging
import asyncio
from collections.abc import Mapping
from typing import Any
import voluptuous as vol

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
from homeassistant.helpers.aiohttp_client import async_get_clientsession

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
        self.tado_device_url: str | None = None
        self.user_code: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigEntry | dict:
        """Handle the initial step of the config flow."""
        if not HAS_PYTADO:
            _LOGGER.error("PyTado library is not available. Install python-tado to use this integration.")
            return self.async_abort(reason="cannot_connect")

        if not HAS_YARL:
            _LOGGER.error("yarl library is not available. Install yarl to use the config flow.")
            return self.async_abort(reason="cannot_connect")

        if user_input is not None:
            # User has seen the form and clicked submit, now we wait.
            return await self.async_step_wait()

        # First time: create Tado instance and get activation URL
        session = async_get_clientsession(self.hass)
        self.tado = Tado(session=session)

        try:
            self.tado_device_url = await self.tado.device_verification_url
            self.user_code = URL(self.tado_device_url).query.get("user_code")
        except Exception:
            _LOGGER.exception("Failed to get device verification URL")
            return self.async_abort(reason="cannot_connect")

        # Show the form with the URL and code
        return self.async_show_form(
            step_id="user",
            description_placeholders={
                "url": self.tado_device_url,
                "code": self.user_code,
            },
            data_schema=vol.Schema({}), # No user input needed on this form
        )

    async def async_step_wait(self, user_input=None) -> config_entries.ConfigEntry | dict:
        """Wait for the user to activate the device on the Tado website."""
        
        async def _wait_for_login() -> None:
            """Inner function to poll for activation."""
            assert self.tado is not None
            try:
                await asyncio.wait_for(
                    self.tado.device_activation(),
                    timeout=DEVICE_ACTIVATION_TIMEOUT,
                )
            except asyncio.TimeoutError:
                _LOGGER.warning("Device activation timed out after %s seconds", DEVICE_ACTIVATION_TIMEOUT)
                raise
            except Exception as ex:
                _LOGGER.exception("Error while waiting for device activation: %s", ex)
                raise

            status = self.tado.device_activation_status()
            if status is not DeviceActivationStatus.COMPLETED:
                raise Exception("Device activation not completed")

        if self.login_task is None:
            self.login_task = self.hass.async_create_task(_wait_for_login())

        # Show progress while we wait
        if not self.login_task.done():
            return self.async_show_progress(
                step_id="wait",
                progress_action="wait_for_device",
                description_placeholders={
                    "url": self.tado_device_url,
                    "code": self.user_code,
                },
                progress_task=self.login_task,
            )

        # Task is done, let's see if it was successful
        try:
            await self.login_task
        except Exception as e:
            _LOGGER.exception("Login task finished with exception: %s", e)
            if isinstance(e, asyncio.TimeoutError):
                return self.async_abort(reason="activation_timeout")
            return self.async_abort(reason="cannot_connect")

        # Activation successful, get refresh token and create entry
        try:
            self.refresh_token = await self.tado.get_refresh_token()
            tado_me = await self.tado.get_me()
        except Exception:
            _LOGGER.exception("Failed to get refresh token or account info from Tado")
            return self.async_abort(reason="cannot_connect")

        if "homes" not in tado_me or not tado_me["homes"]:
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

    async def async_step_reauth(self, data: Mapping[str, Any]) -> config_entries.ConfigEntry | dict:
        """Handle reauthentication."""
        self.login_task = None
        self.tado = None
        return await self.async_step_user()
