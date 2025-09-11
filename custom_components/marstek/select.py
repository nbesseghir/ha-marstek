from __future__ import annotations

from functools import partial

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MarstekCoordinator

MODES = ["Auto", "AI", "Manual", "Passive"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    data = hass.data[DOMAIN][entry.entry_id]
    coord: MarstekCoordinator = data["coordinator"]
    ip = data["ip"]
    device_id = data["device_id"]

    async_add_entities([ModeSelect(coord, ip, device_id)])

class MarstekEntity(CoordinatorEntity[MarstekCoordinator]):
    _attr_has_entity_name = True
    
    def __init__(self, coordinator: MarstekCoordinator, ip: str, device_id: str) -> None:
        super().__init__(coordinator)
        self._ip = ip
        self._device_id = device_id
        self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"marstek_{ip}_{device_id}")},
            name=f"Marstek {ip}",
            manufacturer="Marstek",
            model="Energy Storage",
        )

class ModeSelect(MarstekEntity, SelectEntity):
    _attr_name = "Operating Mode"
    _attr_options = MODES

    def __init__(self, coordinator: MarstekCoordinator, ip: str, device_id: str) -> None:
        super().__init__(coordinator, ip, device_id)
        self._attr_unique_id = f"marstek_{ip}_{device_id}_select_mode"

    @property
    def current_option(self) -> str | None:
        mode = (self.coordinator.data or {}).get("es_mode")
        if not mode:
            return None
        # mode is already a string, not a dict
        m = str(mode).capitalize()
        return m if m in self._attr_options else None

    async def async_select_option(self, option: str) -> None:
        option = option.capitalize()
        if option == "Auto":
            call = partial(self.coordinator.api.set_mode, "Auto", auto_cfg={"enable": 1})
        elif option == "AI":
            call = partial(self.coordinator.api.set_mode, "AI", ai_cfg={"enable": 1})
        elif option == "Manual":
            cfg = {"manual_cfg": {"time_num": 0, "start_time": "08:00", "end_time": "20:00", "week_set": 127, "power": 0, "enable": 1}}
            call = partial(self.coordinator.api.set_mode, "Manual", **cfg)
        else:
            call = partial(self.coordinator.api.set_mode, "Passive", passive_cfg={})
        ok = await self.hass.async_add_executor_job(call)
        if ok:
            await self.coordinator.async_request_refresh()