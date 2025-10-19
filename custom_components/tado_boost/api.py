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

    async def _run(self, func, *args, **kwargs):
        try:
            return await self.hass.async_add_executor_job(lambda: func(*args, **kwargs))
        except Exception as err:
            _LOGGER.debug("PyTado call error: %s", err)
            raise TadoApiError(err)

    async def async_get_zones(self) -> List[Dict]:
        # Return list of zones for all homes
        me = await self._run(self._tado.get_me)
        homes = me.get("homes", []) if isinstance(me, dict) else []
        all_zones: List[Dict] = []
        for home in homes:
            home_id = home.get("id")
            try:
                zones = await self._run(self._tado.get_zones)
            except TadoApiError:
                zones = []
            # zones may be a flat list; attach home context
            for z in zones:
                z["home_id"] = home_id
                all_zones.append(z)
        return all_zones

    async def async_get_all_zone_states(self) -> Dict[int, Dict]:
        """Fetch zones and state for each zone and return mapping by zone id."""
        try:
            me = await self._run(self._tado.get_me)
        except TadoApiError as err:
            raise

        homes = me.get("homes", []) if isinstance(me, dict) else []
        all_states: Dict[int, Dict] = {}

        for home in homes:
            home_id = home.get("id")
            try:
                zones = await self._run(self._tado.get_zones)
            except TadoApiError:
                zones = []

            for z in zones:
                zone_id = z.get("id")
                try:
                    state = await self._run(self._tado.get_zone_state, zone_id)
                except TadoApiError:
                    state = {}
                all_states[int(zone_id)] = {"zone": z, "state": state}

        return all_states

    async def async_set_zone_overlay(self, zone_id: int, duration_minutes: int):
        try:
            return await self._run(
                self._tado.set_zone_overlay, zone_id, duration_minutes
            )
        except TadoApiError as err:
            raise

    async def async_restore_zone_state(self, zone_id: int, original_state: Dict):
        try:
            if not original_state:
                return await self._run(self._tado.reset_zone_overlay, zone_id)
            overlay = original_state.get("overlay")
            if overlay:
                # PyTado may accept similar args for set_zone_overlay; try to set overlay directly
                return await self._run(self._tado.set_zone_overlay, zone_id, overlay)
            return await self._run(self._tado.reset_zone_overlay, zone_id)
        except TadoApiError as err:
            raise
