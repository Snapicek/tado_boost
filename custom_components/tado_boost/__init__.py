from __future__ import annotations

import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import ConfigType

from PyTado.interface import Tado
import PyTado.exceptions

from .const import DOMAIN, DATA_COORDINATOR, API_CLIENT, DEFAULT_SCAN_INTERVAL, CONF_REFRESH_TOKEN
from .api import TadoApi, TadoApiError
from .coordinator import TadoCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # Expect a refresh token in the entry data (device-activation flow)
    if CONF_REFRESH_TOKEN not in entry.data:
        _LOGGER.error("Missing refresh token in config entry")
        return False

    # Create a PyTado instance using saved refresh token
    def create_tado_instance():
        tado = Tado(saved_refresh_token=entry.data[CONF_REFRESH_TOKEN])
        return tado

    try:
        tado = await hass.async_add_executor_job(create_tado_instance)
    except PyTado.exceptions.TadoWrongCredentialsException as err:
        _LOGGER.exception("Invalid Tado credentials")
        return False
    except PyTado.exceptions.TadoException as err:
        _LOGGER.exception("Error creating Tado instance: %s", err)
        return False

    # Create API wrapper
    api = TadoApi(hass, tado, entry)

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
