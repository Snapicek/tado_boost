from __future__ import annotations

import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from PyTado.interface import Tado

from .const import DOMAIN, DATA_COORDINATOR, API_CLIENT, DEFAULT_SCAN_INTERVAL
from .api import TadoApi
from .coordinator import TadoCoordinator
from . import services

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Tado Boost component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tado Boost from a config entry."""
    _LOGGER.debug("Setting up Tado Boost entry: %s", entry.entry_id)

    # This is the correct way to manage the token with Application Credentials
    session = OAuth2Session(hass, entry)
    
    # This will refresh the token if it's expired
    await session.async_ensure_token_valid()

    # Get the token for the PyTado library
    token = entry.data["token"]

    # Create the Tado API instance
    tado = Tado(token=token)

    # Create our API wrapper and coordinator
    api = TadoApi(hass, tado, entry)
    coordinator = TadoCoordinator(hass, api, update_interval=DEFAULT_SCAN_INTERVAL)

    # Perform the first data refresh
    await coordinator.async_config_entry_first_refresh()
    _LOGGER.debug("Initial coordinator refresh complete")

    hass.data[DOMAIN][entry.entry_id] = {
        API_CLIENT: api,
        DATA_COORDINATOR: coordinator,
        "oauth_session": session,
    }

    # Register the services
    services.async_register_services(hass, entry)
    _LOGGER.info("Tado Boost integration setup complete for entry %s", entry.entry_id)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Tado Boost entry: %s", entry.entry_id)

    # Unregister services
    services.async_unregister_services(hass)

    # Remove the integration data
    if hass.data[DOMAIN].pop(entry.entry_id, None):
        _LOGGER.info("Successfully unloaded Tado Boost entry %s", entry.entry_id)
    
    return True
