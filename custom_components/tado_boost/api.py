import logging
from typing import Any, Dict, List

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from PyTado.interface import Tado

_LOGGER = logging.getLogger(__name__)


class TadoApiError(Exception):
    """Custom exception for API errors."""
    pass


class TadoApi:
    """Wrapper for PyTado library calls."""

    def __init__(self, hass: HomeAssistant, tado: Tado, entry: ConfigEntry):
        self.hass = hass
        self._tado = tado
        self._entry = entry
        _LOGGER.debug("TadoApi initialized")

    async def _run(self, func, *args, **kwargs):
        """Run a PyTado function in the executor and handle exceptions."""
        try:
            return await self.hass.async_add_executor_job(lambda: func(*args, **kwargs))
        except Exception as err:
            _LOGGER.error("Error executing Tado function %s: %s", getattr(func, "__name__", repr(func)), err)
            raise TadoApiError(err) from err

    async def async_get_all_zone_states(self) -> Dict[int, Dict]:
        """Fetch all zones and their states for all homes."""
        _LOGGER.debug("Fetching all Tado zone states")
        me = await self._run(self._tado.get_me)
        homes = me.get("homes", []) if isinstance(me, dict) else []
        all_states: Dict[int, Dict] = {}

        for home in homes:
            home_id = home.get("id")
            if not home_id:
                continue

            try:
                zones = await self._run(self._tado.get_zones, home_id)
            except TadoApiError:
                _LOGGER.exception("Failed to get zones for home %s", home_id)
                continue

            for zone in zones:
                zone_id = zone.get("id")
                if not zone_id:
                    continue
                
                # Attach home_id to the zone object for later use
                zone["home_id"] = home_id

                try:
                    state = await self._run(self._tado.get_zone_state, home_id, zone_id)
                    state_data = state.data if hasattr(state, "data") else {}
                    all_states[int(zone_id)] = {"zone": zone, "state": state_data}
                except TadoApiError:
                    _LOGGER.exception("Failed to get state for zone %s in home %s", zone_id, home_id)
                except (ValueError, TypeError):
                    _LOGGER.exception("Error processing state for zone %s", zone_id)

        _LOGGER.debug("Finished fetching states for %d zones", len(all_states))
        return all_states

    async def async_set_boost_overlay(self, home_id: int, zone_id: int, duration_minutes: int):
        """Set a temporary boost overlay on a zone."""
        _LOGGER.debug(
            "Setting boost overlay for home %s, zone %s for %d minutes",
            home_id,
            zone_id,
            duration_minutes,
        )
        # We set a manual temperature of 25°C for the boost duration.
        await self._run(
            self._tado.set_zone_overlay,
            home_id,
            zone_id,
            "MANUAL",  # overlay type
            25.0,  # temperature
            duration_minutes * 60,  # duration in seconds
            "HEATING",  # power
        )

    async def async_clear_overlay(self, home_id: int, zone_id: int):
        """Clear the overlay for a zone, returning it to schedule."""
        _LOGGER.debug("Clearing overlay for home %s, zone %s", home_id, zone_id)
        await self._run(self._tado.reset_zone_overlay, home_id, zone_id)
