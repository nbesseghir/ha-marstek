import logging, asyncio, re
from datetime import timedelta, datetime
from typing import Any, Dict, Callable

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MarstekApiClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class MarstekCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, api: MarstekApiClient, update_interval: timedelta) -> None:
        super().__init__(hass, _LOGGER, name="Marstek Coordinator", update_interval=update_interval)
        self.api = api
        self._last_data: Dict[str, Any] | None = None
        self._last_success: datetime | None = None

    async def _async_update_data(self) -> Dict[str, Any]:
        # read options for smoothing and delays
        entry = next((e for e in self.hass.config_entries.async_entries(DOMAIN) if e.entry_id in self.hass.data.get(DOMAIN, {})), None)
        merged = {}
        if entry:
            merged = {**entry.data, **entry.options}

        get_status: Callable[[], Dict[str, Any] | None] | None = getattr(self.api, "get_status", None)
        if not callable(get_status):
            raise UpdateFailed("API method get_status() is missing — wrong file loaded?")

        # ES.GetStatus
        status = await self.api.get_status()
        if not isinstance(status, dict) or not status:
            if self._last_data:
                data = dict(self._last_data)
                data["_stale"] = True
                return data
            raise UpdateFailed("No valid response from device (ES.GetStatus)")

        # ES.GetMode
        await asyncio.sleep(float(merged.get("inter_call_delay_s", 1)))
        get_mode = getattr(self.api, "get_mode", None)
        if callable(get_mode):
            mode = await self.api.get_mode()
            if isinstance(mode, dict):
                status["_mode"] = mode

        # Bat.GetStatus
        await asyncio.sleep(float(merged.get("inter_call_delay_s", 1)))
        get_bat = getattr(self.api, "get_battery_status", None)
        if callable(get_bat):
            bat = await self.api.get_battery_status()
            if isinstance(bat, dict):
                if "soc" in bat and "bat_soc" not in status:
                    status["bat_soc"] = bat.get("soc")
                for k, v in bat.items():
                    status.setdefault(k, v)

        # Smoothing small power flaps (optional)
        min_delta = int(merged.get("min_power_delta_w", 0) or 0)
        if min_delta > 0 and isinstance(self._last_data, dict):
            for k, v in list(status.items()):
                if isinstance(v, (int, float)) and (k.endswith("_power") or k.endswith("power")):
                    prev = self._last_data.get(k)
                    if isinstance(prev, (int, float)) and abs(float(v) - float(prev)) < float(min_delta):
                        status[k] = prev

        # success -> cache and augment timestamp
        self._last_data = dict(status)
        self._last_success = datetime.utcnow()
        self._last_data["_stale"] = False
        self._last_data["_last_success"] = self._last_success.isoformat() + "Z"
        return self._last_data
