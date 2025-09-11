from __future__ import annotations

from functools import partial

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import UnitOfTime, UnitOfPower

from .const import DOMAIN
from .coordinator import MarstekCoordinator

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    data = hass.data[DOMAIN][entry.entry_id]
    coord: MarstekCoordinator = data["coordinator"]
    ip = data["ip"]
    device_id = data["device_id"]

    entities: list[NumberEntity] = [
        PassivePowerNumber(coord, ip, device_id),
        PassiveCountdownNumber(coord, ip, device_id),
    ]
    async_add_entities(entities)

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

class PassivePowerNumber(MarstekEntity, NumberEntity):
    _attr_name = "Passive Power"
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_native_min_value = 0
    _attr_native_max_value = 10000
    _attr_native_step = 10

    def __init__(self, coordinator: MarstekCoordinator, ip: str, device_id: str) -> None:
        super().__init__(coordinator, ip, device_id)
        self._attr_unique_id = f"marstek_{ip}_{device_id}_num_passive_power"

    @property
    def native_value(self) -> float | None:
        return getattr(self, "_last", None)

    async def async_set_native_value(self, value: float) -> None:
        call = partial(self.coordinator.api.set_mode, "Passive", passive_cfg={"power": int(value)})
        ok = await self.hass.async_add_executor_job(call)
        if ok:
            self._last = float(value)
            await self.coordinator.async_request_refresh()

class PassiveCountdownNumber(MarstekEntity, NumberEntity):
    _attr_name = "Passive Countdown"
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_native_min_value = 0
    _attr_native_max_value = 86400
    _attr_native_step = 10

    def __init__(self, coordinator: MarstekCoordinator, ip: str, device_id: str) -> None:
        super().__init__(coordinator, ip, device_id)
        self._attr_unique_id = f"marstek_{ip}_{device_id}_num_passive_cd"

    @property
    def native_value(self) -> float | None:
        return getattr(self, "_last", None)

    async def async_set_native_value(self, value: float) -> None:
        call = partial(self.coordinator.api.set_mode, "Passive", passive_cfg={"cd_time": int(value)})
        ok = await self.hass.async_add_executor_job(call)
        if ok:
            self._last = float(value)
            await self.coordinator.async_request_refresh()