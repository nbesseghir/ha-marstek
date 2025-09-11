import logging, asyncio
from datetime import timedelta, datetime
from typing import Any, Dict

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MarstekApiClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
INTER_CALL_DELAY = 1  # seconds between API calls

class MarstekCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, api: MarstekApiClient, update_interval: timedelta) -> None:
        super().__init__(hass, _LOGGER, name="Marstek Coordinator", update_interval=update_interval)
        self.api = api
        self._last_data: Dict[str, Any] | None = None
        self._last_success: datetime | None = None

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from the Marstek device."""

        # read options for smoothing and delays
        entry = next((e for e in self.hass.config_entries.async_entries(DOMAIN) if e.entry_id in self.hass.data.get(DOMAIN, {})), None)
        merged = {}
        if entry:
            merged = {**entry.data, **entry.options}

        # ES.GetStatus
        energy_status = await self.api.get_status()
        if not energy_status:
            if self._last_data:
                data = dict(self._last_data)
                data["_stale"] = True
                return data
            raise UpdateFailed("No valid response from device (ES.GetStatus)")

        # Build status dict from dataclass attributes
        status = {}
        if energy_status.bat_soc is not None:
            status["bat_soc"] = energy_status.bat_soc
        if energy_status.bat_cap is not None:
            status["bat_cap"] = energy_status.bat_cap
        if energy_status.pv_power is not None:
            status["pv_power"] = energy_status.pv_power
        if energy_status.ongrid_power is not None:
            status["ongrid_power"] = energy_status.ongrid_power
        if energy_status.offgrid_power is not None:
            status["offgrid_power"] = energy_status.offgrid_power
        if energy_status.bat_power is not None:
            status["bat_power"] = energy_status.bat_power
        if energy_status.total_pv_energy is not None:
            status["total_pv_energy"] = energy_status.total_pv_energy
        if energy_status.total_grid_output_energy is not None:
            status["total_grid_output_energy"] = energy_status.total_grid_output_energy
        if energy_status.total_grid_input_energy is not None:
            status["total_grid_input_energy"] = energy_status.total_grid_input_energy
        if energy_status.total_load_energy is not None:
            status["total_load_energy"] = energy_status.total_load_energy

        # ES.GetMode
        await asyncio.sleep(INTER_CALL_DELAY)
        mode = await self.api.get_mode()
        if mode:
            status["es_mode"] = mode.mode

        # Bat.GetStatus
        await asyncio.sleep(INTER_CALL_DELAY)
        bat_status = await self.api.get_battery_status()
        if bat_status:
            if bat_status.soc is not None:
                status.setdefault("bat_soc", bat_status.soc)
                status.setdefault("soc", bat_status.soc)
            if bat_status.charg_flag is not None:
                status.setdefault("charg_flag", bat_status.charg_flag)
            if bat_status.dischrg_flag is not None:
                status.setdefault("dischrg_flag", bat_status.dischrg_flag)
            if bat_status.bat_temp is not None:
                status.setdefault("bat_temp", bat_status.bat_temp)
            if bat_status.bat_voltage is not None:
                status.setdefault("bat_voltage", bat_status.bat_voltage)
            if bat_status.bat_current is not None:
                status.setdefault("bat_current", bat_status.bat_current)
            if bat_status.bat_capacity is not None:
                status.setdefault("bat_capacity", bat_status.bat_capacity)
            if bat_status.rated_capacity is not None:
                status.setdefault("rated_capacity", bat_status.rated_capacity)
            if bat_status.error_code is not None:
                status.setdefault("error_code", bat_status.error_code)

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
