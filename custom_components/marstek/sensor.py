from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
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

@dataclass
class MarstekSensorEntityDescription(SensorEntityDescription):
    """Describes Marstek sensor entity."""
    scale: float = 1.0
    data_key: str | None = None  # Alternative key to look for in data

SENSOR_DESCRIPTIONS: tuple[MarstekSensorEntityDescription, ...] = (
    # Core battery sensors
    MarstekSensorEntityDescription(
        key="bat_soc",
        translation_key="bat_soc",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        data_key="soc",  # Fallback to "soc" if "bat_soc" not found
    ),
    MarstekSensorEntityDescription(
        key="bat_temp",
        translation_key="bat_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    MarstekSensorEntityDescription(
        key="bat_capacity",
        translation_key="bat_capacity",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        scale=0.01,
    ),
    MarstekSensorEntityDescription(
        key="rated_capacity",
        translation_key="rated_capacity",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        scale=0.001,
    ),
    MarstekSensorEntityDescription(
        key="bat_voltage",
        translation_key="bat_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        scale=0.01,
    ),

    # Power sensors
    MarstekSensorEntityDescription(
        key="bat_power",
        translation_key="bat_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    MarstekSensorEntityDescription(
        key="pv_power",
        translation_key="pv_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    MarstekSensorEntityDescription(
        key="ongrid_power",
        translation_key="ongrid_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    MarstekSensorEntityDescription(
        key="offgrid_power",
        translation_key="offgrid_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),

    # Energy sensors
    MarstekSensorEntityDescription(
        key="total_pv_energy",
        translation_key="total_pv_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
    MarstekSensorEntityDescription(
        key="total_grid_output_energy",
        translation_key="total_grid_output_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        scale=0.01,
    ),
    MarstekSensorEntityDescription(
        key="total_grid_input_energy",
        translation_key="total_grid_input_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        scale=0.01,
    ),
    MarstekSensorEntityDescription(
        key="total_load_energy",
        translation_key="total_load_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    data = hass.data[DOMAIN][entry.entry_id]
    coord: MarstekCoordinator = data["coordinator"]
    ip = data["ip"]
    device_id = data["device_id"]

    entities = [
        MarstekSensor(coord, description, ip, device_id)
        for description in SENSOR_DESCRIPTIONS
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

class MarstekSensor(MarstekEntity, SensorEntity):
    """Marstek sensor entity."""
    
    entity_description: MarstekSensorEntityDescription

    def __init__(
        self,
        coordinator: MarstekCoordinator,
        description: MarstekSensorEntityDescription,
        ip: str,
        device_id: str,
    ) -> None:
        super().__init__(coordinator, ip, device_id)
        self.entity_description = description
        
        safe_key = re.sub(r"[^a-zA-Z0-9_]+", "_", description.key)
        self._attr_unique_id = f"marstek_{ip}_{device_id}_sensor_{safe_key}"

    @property
    def native_value(self) -> Any:
        data = self.coordinator.data or {}
        
        # Try primary key first, then fallback key
        raw = data.get(self.entity_description.key)
        if raw is None and self.entity_description.data_key:
            raw = data.get(self.entity_description.data_key)
        
        try:
            if raw is None:
                return None
            if isinstance(raw, (int, float)):
                return raw * self.entity_description.scale
            if isinstance(raw, str):
                s = raw.replace(',', '.').strip()
                if s.replace('.', '', 1).lstrip('-').isdigit():
                    return float(s) * self.entity_description.scale
        except Exception:
            return raw
        return raw

    @property
    def available(self) -> bool:
        data = self.coordinator.data or {}
        # read option mark_unavailable_on_timeout
        entry = next((e for e in self.hass.config_entries.async_entries(DOMAIN) if e.entry_id in self.hass.data.get(DOMAIN, {})), None)
        merged = {**(entry.data if entry else {}), **(entry.options if entry else {})}
        fail_unavail = bool(merged.get("mark_unavailable_on_timeout", False))
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