from __future__ import annotations

import asyncio
import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .const import DOMAIN, DATA_COORDINATOR, API_CLIENT, DEFAULT_SCAN_INTERVAL
from .api import TadoApi, TadoApiError
from .coordinator import TadoCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    username = entry.data.get("username")
    password = entry.data.get("password")

    api = TadoApi(hass, username, password)

    coordinator = TadoCoordinator(hass, api, update_interval=DEFAULT_SCAN_INTERVAL)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        API_CLIENT: api,
        DATA_COORDINATOR: coordinator,
    }

    # register services
    from . import services
    services.async_register_services(hass, entry)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data = hass.data[DOMAIN].pop(entry.entry_id, None)
    if not data:
        return True
    # cancel coordinator
    await data[DATA_COORDINATOR].async_cancel()
    return True

