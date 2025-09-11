from __future__ import annotations

import re
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import UnitOfPower, UnitOfEnergy, PERCENTAGE, UnitOfElectricCurrent, UnitOfElectricPotential, UnitOfTemperature

from .const import DOMAIN
from .coordinator import MarstekCoordinator

FRIENDLY_NAMES = {
    "soc": "Battery SoC",
    "bat_soc": "Battery SoC",
    "bat_temp": "Battery Temperature",
    "bat_capacity": "Battery Remaining Capacity",
    "rated_capacity": "Battery Rated Capacity",
    "bat_cap": "Battery Capacity",
    "bat_power": "Battery Power",
    "pv_power": "PV Power",
    "ongrid_power": "Grid Export Power",
    "offgrid_power": "Grid Import Power",
    "total_pv_energy": "Total PV Energy",
    "total_grid_output_energy": "Total Grid Export Energy",
    "total_grid_input_energy": "Total Grid Import Energy",
    "total_load_energy": "Total Load Energy",
}

SCALE = {
    "total_grid_output_energy": 0.1,
    "total_grid_input_energy": 0.1,
}

def classify(key: str):
    k = key.lower()
    if k in ("bat_temp",):
        return FRIENDLY_NAMES.get(key, key), UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT
    if k.startswith("total_") and "energy" in k:
        return FRIENDLY_NAMES.get(key, key), UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING
    if k.endswith("_power") or k.endswith("power"):
        return FRIENDLY_NAMES.get(key, key), UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT
    if k in ("bat_soc", "soc") or ("soc" in k and "bat" in k):
        return FRIENDLY_NAMES.get(key, key), PERCENTAGE, SensorDeviceClass.BATTERY, SensorStateClass.MEASUREMENT
    if k == "bat_cap" or ("cap" in k and "bat" in k) or k in ("bat_capacity", "rated_capacity"):
        return FRIENDLY_NAMES.get(key, key), UnitOfEnergy.WATT_HOUR, None, None
    if "volt" in k:
        return FRIENDLY_NAMES.get(key, key), UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT
    if "amp" in k or "current" in k:
        return FRIENDLY_NAMES.get(key, key), UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT
    return FRIENDLY_NAMES.get(key, key), None, None, None

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    data = hass.data[DOMAIN][entry.entry_id]
    coord: MarstekCoordinator = data["coordinator"]
    ip = data["ip"]
    device_id = data["device_id"]

    entities: list[SensorEntity] = []
    added_keys: set[str] = set()

    # Always add Battery sensors
    entities.append(MarstekScalarSensor(coord, ip, device_id, "bat_soc", FRIENDLY_NAMES.get("bat_soc", "Battery SoC"), PERCENTAGE, SensorDeviceClass.BATTERY, SensorStateClass.MEASUREMENT, 1.0))
    added_keys.add("bat_soc")
    entities.append(MarstekScalarSensor(coord, ip, device_id, "bat_temp", FRIENDLY_NAMES.get("bat_temp", "Battery Temperature"), UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT, 1.0))
    added_keys.add("bat_temp")
    entities.append(MarstekScalarSensor(coord, ip, device_id, "bat_capacity", FRIENDLY_NAMES.get("bat_capacity", "Battery Remaining Capacity"), UnitOfEnergy.WATT_HOUR, None, None, 1.0))
    added_keys.add("bat_capacity")
    entities.append(MarstekScalarSensor(coord, ip, device_id, "rated_capacity", FRIENDLY_NAMES.get("rated_capacity", "Battery Rated Capacity"), UnitOfEnergy.WATT_HOUR, None, None, 1.0))
    added_keys.add("rated_capacity")

    # Add sensors for any numeric payload keys
    payload = coord.data or {}
    for key, value in payload.items():
        if isinstance(value, bool) or value is None:
            continue
        if isinstance(value, (int, float)) or (isinstance(value, str) and value.replace('.', '', 1).lstrip('-').isdigit()):
            if key in added_keys:
                continue
            name, unit, dev_class, state_class = classify(key)
            scale = SCALE.get(key, 1.0)
            entities.append(MarstekScalarSensor(coord, ip, device_id, key, name, unit, dev_class, state_class, scale))

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

class MarstekScalarSensor(BaseEntity, SensorEntity):
    def __init__(
        self,
        coordinator: MarstekCoordinator,
        ip: str,
        device_id: str,
        key: str,
        name: str | None,
        unit: str | None,
        device_class: SensorDeviceClass | None,
        state_class: SensorStateClass | None,
        scale: float = 1.0,
    ) -> None:
        super().__init__(coordinator, ip, device_id)
        self._key = key
        self._scale = float(scale or 1.0)
        self._attr_name = name or key
        safe_key = re.sub(r"[^a-zA-Z0-9_]+", "_", key)
        self._attr_unique_id = f"marstek_{ip}_{device_id}_sensor_{safe_key}"
        if unit:
            self._attr_native_unit_of_measurement = unit
        if device_class:
            self._attr_device_class = device_class
        if state_class:
            self._attr_state_class = state_class

    @property
    def native_value(self) -> Any:
        data = self.coordinator.data or {}
        raw = data.get(self._key)
        if raw is None and self._key == "bat_soc":
            raw = data.get("soc")
        try:
            if raw is None:
                return None
            if isinstance(raw, (int, float)):
                return raw * self._scale
            if isinstance(raw, str):
                s = raw.replace(',', '.').strip()
                if s.replace('.', '', 1).lstrip('-').isdigit():
                    return float(s) * self._scale
        except Exception:
            return raw
        return raw

    @property
    def available(self) -> bool:
        data = self.coordinator.data or {}
        # read option fail_unavailable
        entry = next((e for e in self.hass.config_entries.async_entries(DOMAIN) if e.entry_id in self.hass.data.get(DOMAIN, {})), None)
        merged = {**(entry.data if entry else {}), **(entry.options if entry else {})}
        fail_unavail = bool(merged.get("fail_unavailable", False))
        if fail_unavail:
            return bool(data) and not data.get("_stale", False)
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        data = self.coordinator.data or {}
        attrs: dict[str, Any] = {}
        if "_stale" in data:
            attrs["stale"] = bool(data.get("_stale"))
        if "_last_success" in data:
            attrs["last_success"] = data.get("_last_success")
        return attrs or None