from __future__ import annotations

import asyncio
import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers import config_entry_oauth2_flow
from .const import DOMAIN, DATA_COORDINATOR, API_CLIENT, DEFAULT_SCAN_INTERVAL
from .api import TadoApi, TadoApiError
from .coordinator import TadoCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # Use Home Assistant's OAuth2 implementation to manage tokens and reauth
    implementation = await config_entry_oauth2_flow.async_get_config_entry_implementation(hass, entry)

    api = TadoApi(hass, implementation, entry)

    coordinator = TadoCoordinator(hass, api, update_interval=DEFAULT_SCAN_INTERVAL)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        API_CLIENT: api,
        DATA_COORDINATOR: coordinator,
        "implementation": implementation,
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
