from __future__ import annotations

import asyncio
import logging
import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry
from homeassistant.helpers import config_validation as cv
from .const import DOMAIN, API_CLIENT, DATA_COORDINATOR, DEFAULT_BOOST_MINUTES

_LOGGER = logging.getLogger(__name__)

SERVICE_BOOST_ALL = "boost_all_zones"

BOOST_SCHEMA = vol.Schema({vol.Optional("minutes", default=DEFAULT_BOOST_MINUTES): vol.All(int, vol.Range(min=1, max=240))})


def async_register_services(hass: HomeAssistant, entry):
    async def _handle_boost(call: ServiceCall):
        _LOGGER.debug("Boost service called with data: %s", call.data)
        duration = call.data.get("minutes", DEFAULT_BOOST_MINUTES)
        data = hass.data[DOMAIN].get(entry.entry_id)
        if not data:
            _LOGGER.error("Integration data not found for entry %s", entry.entry_id)
            return
        api = data[API_CLIENT]
        coordinator = data[DATA_COORDINATOR]

        # fetch current states once
        try:
            _LOGGER.debug("Fetching current zone states before boost")
            states = await api.async_get_all_zone_states()
        except Exception as err:
            _LOGGER.error("Failed to get zone states: %s", err)
            return

        original_states = {}
        tasks = []
        for zone_id, info in states.items():
            original_states[zone_id] = info.get("state") or {}
            tasks.append(api.async_set_zone_overlay(zone_id, duration))

        # Run set overlay calls concurrently but don't flood API for too many zones
        try:
            _LOGGER.debug("Setting overlays for %d zones for %s minutes", len(tasks), duration)
            await asyncio.gather(*tasks)
        except Exception as err:
            _LOGGER.error("Error setting overlays: %s", err)

        # schedule restoration
        async def _restore():
            _LOGGER.debug("Waiting %s minutes to restore overlays", duration)
            await asyncio.sleep(duration * 60)
            restore_tasks = []
            for zid, orig in original_states.items():
                restore_tasks.append(api.async_restore_zone_state(zid, orig))
            try:
                _LOGGER.debug("Restoring overlays for %d zones", len(restore_tasks))
                await asyncio.gather(*restore_tasks)
            except Exception as err:
                _LOGGER.error("Error restoring zones: %s", err)

        hass.async_create_task(_restore())

    hass.services.async_register(DOMAIN, SERVICE_BOOST_ALL, _handle_boost, schema=BOOST_SCHEMA)


def async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister services for the Tado Boost integration."""
    _LOGGER.debug("Unregistering services for domain %s", DOMAIN)
    hass.services.async_remove(DOMAIN, SERVICE_BOOST_ALL)
