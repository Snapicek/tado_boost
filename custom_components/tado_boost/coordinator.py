from __future__ import annotations

import logging
from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import HomeAssistant
from .api import TadoApi, TadoApiError

_LOGGER = logging.getLogger(__name__)

class TadoCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, api: TadoApi, update_interval: int = 60):
        super().__init__(
            hass,
            _LOGGER,
            name="Tado Boost Coordinator",
            update_interval=timedelta(seconds=update_interval),
        )
        self.api = api

    async def _async_update_data(self):
        try:
            data = await self.api.async_get_all_zone_states()
            return data
        except TadoApiError as err:
            raise UpdateFailed(err)

