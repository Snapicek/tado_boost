from __future__ import annotations

import asyncio
import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .api import TadoApiError
from .const import (
    API_CLIENT,
    DATA_COORDINATOR,
    DEFAULT_BOOST_MINUTES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_BOOST_ALL = "boost_all_zones"

BOOST_SCHEMA = vol.Schema(
    {
        vol.Optional("minutes", default=DEFAULT_BOOST_MINUTES): vol.All(
            int, vol.Range(min=1, max=240)
        )
    }
)


def async_register_services(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Register services for the Tado Boost integration."""

    async def _handle_boost(call: ServiceCall) -> None:
        """Handle the boost_all_zones service call."""
        duration = call.data["minutes"]
        _LOGGER.info("Tado Boost service called for %d minutes", duration)

        data = hass.data[DOMAIN].get(entry.entry_id)
        if not data:
            _LOGGER.error("Integration data not found for entry %s", entry.entry_id)
            return

        api = data[API_CLIENT]
        coordinator = data[DATA_COORDINATOR]

        if not coordinator.data:
            _LOGGER.warning("No zone data available. Requesting refresh...")
            await coordinator.async_request_refresh()
            if not coordinator.data:
                _LOGGER.error("Failed to fetch zone data. Cannot apply boost.")
                return

        zones_to_boost = []
        for zone_id, info in coordinator.data.items():
            zone_info = info.get("zone")
            if zone_info and (home_id := zone_info.get("home_id")):
                zones_to_boost.append({"home_id": home_id, "zone_id": zone_id})

        if not zones_to_boost:
            _LOGGER.warning("No zones found to boost.")
            return

        _LOGGER.info("Applying boost to %d zones...", len(zones_to_boost))
        boost_tasks = [
            api.async_set_boost_overlay(
                home_id=zone["home_id"],
                zone_id=zone["zone_id"],
                duration_minutes=duration,
            )
            for zone in zones_to_boost
        ]

        try:
            await asyncio.gather(*boost_tasks)
            _LOGGER.info("Successfully applied boost to %d zones.", len(zones_to_boost))
        except TadoApiError:
            _LOGGER.exception("An error occurred while setting boost overlays.")
            return  # Do not schedule clear if boost failed

        # Schedule the task to clear the overlays
        async def _clear_boosts():
            await asyncio.sleep(duration * 60)
            _LOGGER.info("Clearing overlays for %d zones.", len(zones_to_boost))
            clear_tasks = [
                api.async_clear_overlay(home_id=zone["home_id"], zone_id=zone["zone_id"])
                for zone in zones_to_boost
            ]
            try:
                await asyncio.gather(*clear_tasks)
                _LOGGER.info("Successfully cleared overlays.")
            except TadoApiError:
                _LOGGER.exception("An error occurred while clearing overlays.")

        hass.async_create_task(_clear_boosts())

    hass.services.async_register(
        DOMAIN, SERVICE_BOOST_ALL, _handle_boost, schema=BOOST_SCHEMA
    )


def async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister services for the Tado Boost integration."""
    hass.services.async_remove(DOMAIN, SERVICE_BOOST_ALL)
