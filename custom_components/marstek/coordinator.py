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
        # read options for retries/backoff + smoothing
        entry = next((e for e in self.hass.config_entries.async_entries(DOMAIN) if e.entry_id in self.hass.data.get(DOMAIN, {})), None)
        merged = {}
        if entry:
            merged = {**entry.data, **entry.options}
        retries = int(merged.get("retries", 2))
        backoff = float(merged.get("backoff", 0.2))

        get_status: Callable[[], Dict[str, Any] | None] | None = getattr(self.api, "get_status", None)
        if not callable(get_status):
            raise UpdateFailed("API method get_status() is missing — wrong file loaded?")

        status: Dict[str, Any] | None = None

        # retry loop (configurable attempts)
        for i in range(max(1, retries)):
            status = await self.hass.async_add_executor_job(get_status)
            if isinstance(status, dict) and status:
                break
            await asyncio.sleep(max(0.05, backoff) * (i + 1))

        if not isinstance(status, dict) or not status:
            if self._last_data:
                data = dict(self._last_data)
                data["_stale"] = True
                return data
            raise UpdateFailed("No valid response from device (ES.GetStatus)")

        # fetch mode (best-effort)
        get_mode = getattr(self.api, "get_mode", None)
        if callable(get_mode):
            for i in range(max(1, min(2, retries))):
                mode = await self.hass.async_add_executor_job(get_mode)
                if isinstance(mode, dict):
                    status["_mode"] = mode
                    break
                await asyncio.sleep(max(0.05, backoff) * (i + 1))

        # fetch battery status (best-effort)
        get_bat = getattr(self.api, "get_battery_status", None)
        if callable(get_bat):
            for i in range(max(1, min(2, retries))):
                bat = await self.hass.async_add_executor_job(get_bat)
                if isinstance(bat, dict):
                    if "soc" in bat and "bat_soc" not in status:
                        status["bat_soc"] = bat.get("soc")
                    for k, v in bat.items():
                        status.setdefault(k, v)
                    break
                await asyncio.sleep(max(0.05, backoff) * (i + 1))

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
