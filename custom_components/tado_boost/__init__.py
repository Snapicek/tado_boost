from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .api import TadoBoostApi
from .const import (
    API_CLIENT,
    CONF_REFRESH_TOKEN,
    DATA_COORDINATOR,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .coordinator import TadoCoordinator
from . import services

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Tado Boost component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tado Boost from a config entry using the tado-assist architecture."""
    _LOGGER.debug("Setting up Tado Boost entry: %s", entry.entry_id)

    refresh_token = entry.data.get(CONF_REFRESH_TOKEN)
    if not refresh_token:
        _LOGGER.error("Missing refresh token in config entry %s", entry.entry_id)
        return False

    # Create the stateful API instance, which will manage the token
    api = TadoBoostApi(hass, entry, refresh_token=refresh_token)
    
    # Initialize it to confirm the token is valid and get initial status
    try:
        await api.async_initialize()
    except Exception as err:
        _LOGGER.exception("Error initializing Tado API with refresh token: %s", err)
        return False

    coordinator = TadoCoordinator(hass, api, update_interval=DEFAULT_SCAN_INTERVAL)

    await coordinator.async_config_entry_first_refresh()
    _LOGGER.debug("Initial coordinator refresh complete")

    hass.data[DOMAIN][entry.entry_id] = {
        API_CLIENT: api,
        DATA_COORDINATOR: coordinator,
    }

    services.async_register_services(hass, entry)
    _LOGGER.info("Tado Boost integration setup complete for entry %s", entry.entry_id)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Tado Boost entry: %s", entry.entry_id)

    services.async_unregister_services(hass)

    if hass.data[DOMAIN].pop(entry.entry_id, None):
        _LOGGER.info("Successfully unloaded Tado Boost entry %s", entry.entry_id)

    return True
