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
    _LOGGER.debug("%s: async_setup called", DOMAIN)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _LOGGER.debug("%s: async_setup_entry starting for entry_id=%s", DOMAIN, entry.entry_id)
    # Expect a refresh token in the entry data (device-activation flow)
    if CONF_REFRESH_TOKEN not in entry.data:
        _LOGGER.error("Missing refresh token in config entry %s", entry.entry_id)
        return False

    # Create a PyTado instance using saved refresh token
    def create_tado_instance():
        _LOGGER.debug("Creating PyTado instance from refresh token")
        tado = Tado(saved_refresh_token=entry.data[CONF_REFRESH_TOKEN])
        return tado

    try:
        tado = await hass.async_add_executor_job(create_tado_instance)
        _LOGGER.debug("PyTado instance created successfully")
    except PyTado.exceptions.TadoWrongCredentialsException as err:
        _LOGGER.exception("Invalid Tado credentials")
        return False
    except PyTado.exceptions.TadoException as err:
        _LOGGER.exception("Error creating Tado instance: %s", err)
        return False

    # Create API wrapper
    api = TadoApi(hass, tado, entry)
    _LOGGER.debug("TadoApi wrapper created")

    coordinator = TadoCoordinator(hass, api, update_interval=DEFAULT_SCAN_INTERVAL)
    _LOGGER.debug("TadoCoordinator created, performing first refresh")
    await coordinator.async_config_entry_first_refresh()
    _LOGGER.debug("First coordinator refresh done")

    hass.data[DOMAIN][entry.entry_id] = {
        API_CLIENT: api,
        DATA_COORDINATOR: coordinator,
    }

    # register services
    from . import services
    services.async_register_services(hass, entry)
    _LOGGER.debug("Services registered for entry %s", entry.entry_id)

    _LOGGER.info("%s integration setup complete for entry %s", DOMAIN, entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _LOGGER.debug("Unloading entry %s for %s", entry.entry_id, DOMAIN)
    data = hass.data[DOMAIN].pop(entry.entry_id, None)
    if not data:
        _LOGGER.debug("No data found for entry %s during unload", entry.entry_id)
        return True
    # cancel coordinator
    await data[DATA_COORDINATOR].async_cancel()
    _LOGGER.info("Unloaded entry %s for %s", entry.entry_id, DOMAIN)
    return True
