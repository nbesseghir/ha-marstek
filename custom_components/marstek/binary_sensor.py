from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
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

    entities: list[BinarySensorEntity] = [
        ChargePermissionBinary(coord, ip, device_id),
        DischargePermissionBinary(coord, ip, device_id),
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

class ChargePermissionBinary(MarstekEntity, BinarySensorEntity):
    _attr_name = "Battery Charging Allowed"
    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING

    def __init__(self, coordinator: MarstekCoordinator, ip: str, device_id: str) -> None:
        super().__init__(coordinator, ip, device_id)
        self._attr_unique_id = f"marstek_{ip}_{device_id}_bin_charg_flag"

    @property
    def available(self) -> bool:
        data = self.coordinator.data or {}
        entry = next((e for e in self.hass.config_entries.async_entries(DOMAIN) if e.entry_id in self.hass.data.get(DOMAIN, {})), None)
        merged = {**(entry.data if entry else {}), **(entry.options if entry else {})}
        fail_unavail = bool(merged.get("mark_unavailable_on_timeout", False))
        if fail_unavail:
            return bool(data) and not data.get("_stale", False)
        return True

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data or {}
        val = data.get("charg_flag")
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return bool(val)
        return None

class DischargePermissionBinary(MarstekEntity, BinarySensorEntity):
    _attr_name = "Battery Discharging Allowed"

    def __init__(self, coordinator: MarstekCoordinator, ip: str, device_id: str) -> None:
        super().__init__(coordinator, ip, device_id)
        self._attr_unique_id = f"marstek_{ip}_{device_id}_bin_dischrg_flag"

    @property
    def available(self) -> bool:
        data = self.coordinator.data or {}
        entry = next((e for e in self.hass.config_entries.async_entries(DOMAIN) if e.entry_id in self.hass.data.get(DOMAIN, {})), None)
        merged = {**(entry.data if entry else {}), **(entry.options if entry else {})}
        fail_unavail = bool(merged.get("mark_unavailable_on_timeout", False))
        if fail_unavail:
            return bool(data) and not data.get("_stale", False)
        return True

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data or {}
        val = data.get("dischrg_flag")
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return bool(val)
        return None