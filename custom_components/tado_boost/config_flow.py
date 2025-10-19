from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from PyTado.exceptions import TadoException
from PyTado.interface import Tado
from yarl import URL

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_REFRESH_TOKEN, DOMAIN

_LOGGER = logging.getLogger(__name__)

DEVICE_ACTIVATION_TIMEOUT = 120


class TadoBoostFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tado Boost."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow handler."""
        self.tado: Tado | None = None
        self.tado_device_url: str | None = None
        self.user_code: str | None = None
        self.login_task: asyncio.Task | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step of the device activation flow."""
        if user_input is not None:
            # User has seen the code and clicked submit, move to the wait step
            return await self.async_step_wait()

        try:
            self.tado = await self.hass.async_add_executor_job(Tado)
            self.tado_device_url = await self.hass.async_add_executor_job(
                self.tado.device_verification_url
            )
            self.user_code = URL(self.tado_device_url).query.get("user_code")
        except (TadoException, Exception) as e:
            _LOGGER.exception("Failed to get Tado device verification URL: %s", e)
            return self.async_abort(reason="cannot_connect")

        return self.async_show_form(
            step_id="user",
            description_placeholders={
                "url": self.tado_device_url,
                "code": self.user_code,
            },
            data_schema=vol.Schema({}), # No user input needed on this form
        )

    async def async_step_wait(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Wait for the user to authorize the device on the Tado website."""
        if not self.login_task:
            self.login_task = self.hass.async_create_task(self._wait_for_login())

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
        
        try:
            await self.login_task
        except Exception as e:
            _LOGGER.exception("Device activation failed: %s", e)
            if isinstance(e, asyncio.TimeoutError):
                return self.async_show_progress_done(next_step_id="timed_out")
            return self.async_show_progress_done(next_step_id="activation_error")

        return self.async_show_progress_done(next_step_id="finish_login")
    
    async def async_step_timed_out(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Show timeout error and offer to retry."""
        return self.async_abort(reason="activation_timeout")

    async def async_step_activation_error(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Show a generic activation error."""
        return self.async_abort(reason="cannot_connect")

    async def async_step_finish_login(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Finish the login process after successful device activation."""
        assert self.tado is not None
        try:
            refresh_token = await self.hass.async_add_executor_job(self.tado.get_refresh_token)
            tado_me = await self.hass.async_add_executor_job(self.tado.get_me)
        except Exception as e:
            _LOGGER.exception("Failed to get refresh token or account info: %s", e)
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
            data={CONF_REFRESH_TOKEN: refresh_token},
        )

    async def _wait_for_login(self) -> None:
        """Poll Tado until the device activation is completed."""
        assert self.tado is not None
        await asyncio.wait_for(
            self.hass.async_add_executor_job(self.tado.device_activation),
            timeout=DEVICE_ACTIVATION_TIMEOUT,
        )
