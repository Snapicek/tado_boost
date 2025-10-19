from __future__ import annotations

import asyncio
import logging
import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, API_CLIENT, DATA_COORDINATOR, DEFAULT_BOOST_MINUTES
from .api import TadoApiError

_LOGGER = logging.getLogger(__name__)

SERVICE_BOOST_ALL = "boost_all_zones"

BOOST_SCHEMA = vol.Schema(
    {
        vol.Optional("minutes", default=DEFAULT_BOOST_MINUTES): vol.All(
            int, vol.Range(min=1, max=240)
        )
    }
)


def async_register_services(hass: HomeAssistant, entry: ConfigEntry):
    """Register services for the Tado Boost integration."""

    async def _handle_boost(call: ServiceCall) -> None:
        """Handle the boost_all_zones service call."""
        duration = call.data.get("minutes", DEFAULT_BOOST_MINUTES)
        _LOGGER.info("Tado Boost service called for %d minutes", duration)

        data = hass.data[DOMAIN].get(entry.entry_id)
        if not data:
            _LOGGER.error("Integration data not found for entry %s", entry.entry_id)
            return

        api = data[API_CLIENT]
        coordinator = data[DATA_COORDINATOR]

        if not coordinator.data:
            _LOGGER.warning("No zone data available in coordinator. Refreshing...")
            await coordinator.async_request_refresh()
            if not coordinator.data:
                _LOGGER.error("Failed to fetch zone data. Cannot apply boost.")
                return

        zones_to_boost = []
        for zone_id, info in coordinator.data.items():
            zone_info = info.get("zone")
            if not zone_info:
                continue
            
            home_id = zone_info.get("home_id")
            if home_id:
                zones_to_boost.append({"home_id": home_id, "zone_id": zone_id})

        if not zones_to_boost:
            _LOGGER.warning("No zones found to boost.")
            return

        _LOGGER.info("Applying boost to %d zones...", len(zones_to_boost))
        boost_tasks = []
        for zone in zones_to_boost:
            boost_tasks.append(
                api.async_set_boost_overlay(
                    home_id=zone["home_id"],
                    zone_id=zone["zone_id"],
                    duration_minutes=duration,
                )
            )
        
        try:
            await asyncio.gather(*boost_tasks)
            _LOGGER.info("Successfully applied boost to %d zones.", len(zones_to_boost))
        except TadoApiError:
            _LOGGER.exception("An error occurred while setting boost overlays.")
            # Don't schedule clear if boost failed
            return

        # Schedule the task to clear the overlays after the duration
        async def _clear_boosts():
            await asyncio.sleep(duration * 60)
            _LOGGER.info("Boost duration of %d minutes finished. Clearing overlays...", duration)
            clear_tasks = []
            for zone in zones_to_boost:
                clear_tasks.append(
                    api.async_clear_overlay(
                        home_id=zone["home_id"], zone_id=zone["zone_id"]
                    )
                )
            try:
                await asyncio.gather(*clear_tasks)
                _LOGGER.info("Successfully cleared overlays for %d zones.", len(zones_to_boost))
            except TadoApiError:
                _LOGGER.exception("An error occurred while clearing overlays.")

        hass.async_create_task(_clear_boosts())

    hass.services.async_register(
        DOMAIN, SERVICE_BOOST_ALL, _handle_boost, schema=BOOST_SCHEMA
    )


def async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister services for the Tado Boost integration."""
    _LOGGER.debug("Unregistering services for domain %s", DOMAIN)
    hass.services.async_remove(DOMAIN, SERVICE_BOOST_ALL)
