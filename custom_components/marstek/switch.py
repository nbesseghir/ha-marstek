from __future__ import annotations

from typing import Any
from functools import partial

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MarstekCoordinator

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    data = hass.data[DOMAIN][entry.entry_id]
    coord: MarstekCoordinator = data["coordinator"]
    ip = data["ip"]
    device_id = data["device_id"]

    entities: list[SwitchEntity] = [
        ModeSwitch(coord, ip, device_id, "Auto"),
        ModeSwitch(coord, ip, device_id, "AI"),
        ModeSwitch(coord, ip, device_id, "Passive"),
    ]
    async_add_entities(entities)

class BaseEntity(CoordinatorEntity[MarstekCoordinator]):
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

class ModeSwitch(BaseEntity, SwitchEntity):
    def __init__(self, coordinator: MarstekCoordinator, ip: str, device_id: str, mode: str) -> None:
        super().__init__(coordinator, ip, device_id)
        self._mode = mode
        self._attr_name = f"{mode} Mode"
        key = mode.lower()
        self._attr_unique_id = f"marstek_{ip}_{device_id}_switch_mode_{key}"

    @property
    def is_on(self) -> bool | None:
        mode = (self.coordinator.data or {}).get("_mode") or {}
        cur = str(mode.get("mode") or "").capitalize()
        return cur == self._mode

    async def async_turn_on(self, **kwargs: Any) -> None:
        cfg_key = {"Auto": "auto_cfg", "AI": "ai_cfg", "Passive": "passive_cfg"}.get(self._mode)
        if cfg_key in ("auto_cfg", "ai_cfg"):
            call = partial(self.coordinator.api.set_mode, self._mode, **{cfg_key: {"enable": 1}})
        else:
            call = partial(self.coordinator.api.set_mode, self._mode, passive_cfg={})
        ok = await self.hass.async_add_executor_job(call)
        if ok:
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        call = partial(self.coordinator.api.set_mode, "Auto", auto_cfg={"enable": 1})
        ok = await self.hass.async_add_executor_job(call)
        if ok:
            await self.coordinator.async_request_refresh()