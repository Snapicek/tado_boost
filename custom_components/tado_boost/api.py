import logging
from typing import Any, Dict, List

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class TadoApiError(Exception):
    pass


class TadoApi:
    """Thin wrapper around a PyTado Tado instance, executed in the HA executor."""

    def __init__(self, hass: HomeAssistant, tado, entry):
        self.hass = hass
        self._tado = tado
        self._entry = entry
        _LOGGER.debug("TadoApi initialized for entry %s", getattr(entry, "entry_id", None))

    async def _run(self, func, *args, **kwargs):
        try:
            _LOGGER.debug("Running PyTado function %s with args=%s kwargs=%s", getattr(func, "__name__", repr(func)), args, kwargs)
            return await self.hass.async_add_executor_job(lambda: func(*args, **kwargs))
        except Exception as err:
            _LOGGER.debug("PyTado call error: %s", err)
            raise TadoApiError(err)

    async def async_get_zones(self) -> List[Dict]:
        # Return list of zones for all homes
        _LOGGER.debug("async_get_zones called")
        me = await self._run(self._tado.get_me)
        homes = me.get("homes", []) if isinstance(me, dict) else []
        all_zones: List[Dict] = []
        for home in homes:
            home_id = home.get("id")
            try:
                zones = await self._run(self._tado.get_zones)
            except TadoApiError:
                _LOGGER.exception("Failed getting zones for home %s", home_id)
                zones = []
            # zones may be a flat list; attach home context
            for z in zones:
                z["home_id"] = home_id
                all_zones.append(z)
        _LOGGER.debug("async_get_zones returning %d zones", len(all_zones))
        return all_zones

    async def async_get_all_zone_states(self) -> Dict[int, Dict]:
        """Fetch zones and state for each zone and return mapping by zone id."""
        _LOGGER.debug("async_get_all_zone_states called")
        try:
            me = await self._run(self._tado.get_me)
        except TadoApiError as err:
            _LOGGER.debug("Failed to get 'me' from Tado: %s", err)
            raise

        homes = me.get("homes", []) if isinstance(me, dict) else []
        all_states: Dict[int, Dict] = {}

        for home in homes:
            home_id = home.get("id")
            try:
                zones = await self._run(self._tado.get_zones)
            except TadoApiError:
                _LOGGER.exception("Failed getting zones for home %s", home_id)
                zones = []

            for z in zones:
                zone_id = z.get("id")
                try:
                    state = await self._run(self._tado.get_zone_state, zone_id)
                except TadoApiError:
                    _LOGGER.exception("Failed getting state for zone %s", zone_id)
                    state = {}
                try:
                    all_states[int(zone_id)] = {"zone": z, "state": state}
                except Exception:
                    _LOGGER.exception("Error storing state for zone %s", zone_id)

        _LOGGER.debug("async_get_all_zone_states returning %d zone states", len(all_states))
        return all_states

    async def async_set_zone_overlay(self, zone_id: int, duration_minutes: int):
        _LOGGER.debug("async_set_zone_overlay called for zone %s duration %s", zone_id, duration_minutes)
        try:
            return await self._run(
                self._tado.set_zone_overlay, zone_id, duration_minutes
            )
        except TadoApiError as err:
            _LOGGER.exception("Error setting overlay for zone %s: %s", zone_id, err)
            raise

    async def async_restore_zone_state(self, zone_id: int, original_state: Dict):
        _LOGGER.debug("async_restore_zone_state called for zone %s", zone_id)
        try:
            if not original_state:
                _LOGGER.debug("Original state empty, resetting overlay for zone %s", zone_id)
                return await self._run(self._tado.reset_zone_overlay, zone_id)
            overlay = original_state.get("overlay")
            if overlay:
                _LOGGER.debug("Restoring overlay for zone %s: %s", zone_id, overlay)
                # PyTado may accept similar args for set_zone_overlay; try to set overlay directly
                return await self._run(self._tado.set_zone_overlay, zone_id, overlay)
            _LOGGER.debug("No overlay in original state, resetting overlay for zone %s", zone_id)
            return await self._run(self._tado.reset_zone_overlay, zone_id)
        except TadoApiError as err:
            _LOGGER.exception("Error restoring overlay for zone %s: %s", zone_id, err)
            raise
