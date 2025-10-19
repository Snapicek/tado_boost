import asyncio
import logging
from typing import Any, Dict, List
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import config_entry_oauth2_flow

_LOGGER = logging.getLogger(__name__)

# NOTE: This API client is a thin wrapper around Tado's public endpoints.
# It uses Home Assistant's OAuth helper to obtain and refresh access tokens.

class TadoApiError(Exception):
    pass

class TadoApi:
    def __init__(self, hass, implementation, entry):
        """Initialize with Home Assistant, OAuth implementation and config entry.

        implementation: the object returned by async_get_config_entry_implementation
        entry: the ConfigEntry for this integration
        """
        self.hass = hass
        self._implementation = implementation
        self._entry = entry
        self._session = async_get_clientsession(hass)
        self._base = "https://my.tado.com"

    async def _async_get_access_token(self) -> str:
        """Ensure token is valid and return access token string."""
        try:
            token = await config_entry_oauth2_flow.async_ensure_token_valid(
                self.hass, self._implementation, self._entry
            )
            return token.get("access_token")
        except Exception as err:
            _LOGGER.debug("Failed to ensure token valid: %s", err)
            raise TadoApiError(err)

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        headers = kwargs.pop("headers", {}) or {}
        try:
            access_token = await self._async_get_access_token()
            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"
            resp = await self._session.request(method, f"{self._base}{path}", headers=headers, timeout=30, **kwargs)
            if resp.status == 401:
                # token expired/invalid - try once to refresh and retry
                _LOGGER.debug("Received 401, attempting token refresh and retry")
                # invalidate and re-ensure token
                token = await config_entry_oauth2_flow.async_ensure_token_valid(
                    self.hass, self._implementation, self._entry, allow_user_interaction=False
                )
                access_token = token.get("access_token")
                if access_token:
                    headers["Authorization"] = f"Bearer {access_token}"
                    resp = await self._session.request(method, f"{self._base}{path}", headers=headers, timeout=30, **kwargs)
            resp.raise_for_status()
            # Try to return JSON when possible
            try:
                return await resp.json()
            except Exception:
                return await resp.text()
        except TadoApiError:
            raise
        except Exception as err:
            _LOGGER.debug("API request error %s %s: %s", method, path, err)
            raise TadoApiError(err)

    async def async_get_zones(self) -> List[Dict]:
        """Return list of homes/zones (depends on Tado API)."""
        return await self._request("GET", "/api/v2/homes")

    async def async_get_all_zone_states(self) -> Dict[int, Dict]:
        """Fetch all zones and their states with minimal calls.

        This implementation tries to reuse endpoints that return batches. If API
        requires per-zone calls, it will still perform them but callers should be
        mindful of rate limits.
        """
        homes = await self._request("GET", "/api/v2/homes")
        all_states = {}
        for home in homes:
            home_id = home.get("id")
            try:
                zones = await self._request("GET", f"/api/v2/homes/{home_id}/zones")
            except TadoApiError:
                zones = []
            for z in zones:
                zone_id = z.get("id")
                try:
                    state = await self._request("GET", f"/api/v2/zones/{zone_id}/state")
                except TadoApiError:
                    state = {}
                all_states[zone_id] = {"zone": z, "state": state}
        return all_states

    async def async_set_zone_overlay(self, zone_id: int, duration_minutes: int):
        payload = {"type": "MANUAL", "setting": {"type": "HEATING", "power": "ON"}, "termination": {"type": "TIMER", "durationInSeconds": duration_minutes * 60}}
        return await self._request("PUT", f"/api/v2/zones/{zone_id}/overlay", json=payload)

    async def async_restore_zone_state(self, zone_id: int, original_state: Dict):
        # Simplified restoration: if original overlay existed, restore it; else clear overlay
        if not original_state:
            # delete overlay
            return await self._request("DELETE", f"/api/v2/zones/{zone_id}/overlay")
        overlay = original_state.get("overlay")
        if overlay:
            return await self._request("PUT", f"/api/v2/zones/{zone_id}/overlay", json=overlay)
        return await self._request("DELETE", f"/api/v2/zones/{zone_id}/overlay")
