import logging
from typing import Any, Dict

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from PyTado.interface import Tado
from yarl import URL

_LOGGER = logging.getLogger(__name__)


class TadoApiError(Exception):
    """Custom exception for API errors."""
    pass


class TadoBoostApi:
    """A stateful API client for Tado, inspired by tado-assist."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry | None, refresh_token: str | None = None):
        self.hass = hass
        self._entry = entry
        self._tado: Tado | None = None
        self.auth_url: str | None = None
        self.user_code: str | None = None
        self.refresh_token = refresh_token
        self._activation_status: str | None = None

    async def async_initialize(self, force_new: bool = False) -> str:
        """Initialize the Tado client and return the activation status."""
        if self._tado and not force_new:
            _LOGGER.debug("Using existing Tado instance")
        else:
            _LOGGER.debug("Creating new Tado instance (force_new=%s)", force_new)
            # Initialize Tado without refresh_token in constructor
            self._tado = await self.hass.async_add_executor_job(
                lambda: Tado()
            )
            # If a refresh token is available, set it on the Tado object
            if self.refresh_token:
                await self.hass.async_add_executor_job(
                    lambda: setattr(self._tado, 'refresh_token', self.refresh_token)
                )

        status = await self.hass.async_add_executor_job(self._tado.device_activation_status)
        self._activation_status = status
        _LOGGER.debug("Tado activation status: %s", status)

        if status in ["NOT_STARTED", "PENDING"]:
            verification_url = await self.hass.async_add_executor_job(self._tado.device_verification_url)
            self.auth_url = verification_url
            self.user_code = URL(verification_url).query.get("user_code")
            _LOGGER.debug("Tado auth URL: %s", self.auth_url)
        
        await self._check_and_update_token()
        return status

    async def async_activate_device(self) -> bool:
        """Attempt to activate the device and return True on success."""
        _LOGGER.debug("Attempting to activate device...")
        await self.hass.async_add_executor_job(self._tado.device_activation)
        status = await self.hass.async_add_executor_job(self._tado.device_activation_status)
        self._activation_status = status
        _LOGGER.debug("Status after activation attempt: %s", status)

        await self._check_and_update_token()
        return status == "COMPLETED"

    async def async_authenticate(self) -> bool:
        """Authenticate with Tado using the refresh token."""
        if not self.refresh_token:
            _LOGGER.error("Authentication called without a refresh token.")
            return False

        _LOGGER.debug("Attempting to authenticate with refresh token.")
        
        if not self._tado:
            self._tado = await self.hass.async_add_executor_job(lambda: Tado())

        await self.hass.async_add_executor_job(
            lambda: setattr(self._tado, 'refresh_token', self.refresh_token)
        )

        try:
            me = await self._run(self._tado.get_me)
            if not me:
                _LOGGER.error("Authentication failed: get_me returned no data.")
                return False
            
            self._activation_status = "COMPLETED"
            _LOGGER.info("Successfully authenticated with Tado.")
            await self._check_and_update_token()
            return True
        except TadoApiError as err:
            _LOGGER.exception("Authentication failed during API call: %s", err)
            return False

    async def _check_and_update_token(self):
        """Update the stored refresh token if it has changed."""
        try:
            current_token = await self.hass.async_add_executor_job(self._tado.get_refresh_token)
            if current_token and current_token != self.refresh_token:
                _LOGGER.info("Tado refresh token has changed, updating.")
                self.refresh_token = current_token
                if self._entry:
                    data = {**self._entry.data, "refresh_token": current_token}
                    self.hass.config_entries.async_update_entry(self._entry, data=data)
        except Exception as e:
            _LOGGER.warning("Failed to check or update Tado refresh token: %s", e)

    async def async_get_all_zone_states(self) -> Dict[int, Dict]:
        """Fetch all zones and their states for all homes."""
        if self._activation_status != "COMPLETED":
            raise TadoApiError("API called before authentication was complete.")
        
        me = await self._run(self._tado.get_me)
        homes = me.get("homes", []) if isinstance(me, dict) else []
        all_states: Dict[int, Dict] = {}

        for home in homes:
            home_id = home.get("id")
            if not home_id: continue

            zones = await self._run(self._tado.get_zones, home_id)
            for zone in zones:
                zone_id = zone.get("id")
                if not zone_id: continue
                
                zone["home_id"] = home_id
                state = await self._run(self._tado.get_zone_state, home_id, zone_id)
                all_states[int(zone_id)] = {"zone": zone, "state": state.data}

        return all_states

    async def async_set_boost_overlay(self, home_id: int, zone_id: int, duration_minutes: int):
        """Set a temporary boost overlay on a zone."""
        await self._run(
            self._tado.set_zone_overlay,
            home_id, zone_id, "MANUAL", 25.0, duration_minutes * 60, "HEATING"
        )

    async def async_clear_overlay(self, home_id: int, zone_id: int):
        """Clear the overlay for a zone."""
        await self._run(self._tado.reset_zone_overlay, home_id, zone_id)

    async def _run(self, func, *args, **kwargs):
        """Run a PyTado function in the executor and handle exceptions."""
        try:
            return await self.hass.async_add_executor_job(lambda: func(*args, **kwargs))
        except Exception as err:
            _LOGGER.error("Error executing Tado function %s: %s", getattr(func, "__name__", repr(func)), err)
            await self._check_and_update_token() # Refresh token on error
            raise TadoApiError(err) from err
