"""Sensor platform: the A/C's live power draw (from status DPID 0x1C)."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfPower
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AcConfigEntry
from .const import DOMAIN
from .coordinator import AcCoordinator


async def async_setup_entry(hass, entry: AcConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([AcPowerSensor(entry.runtime_data, entry)])


class AcPowerSensor(CoordinatorEntity[AcCoordinator], SensorEntity):
    """Live power draw reported by the A/C."""

    _attr_has_entity_name = True
    _attr_translation_key = "power_draw"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: AcCoordinator, entry: AcConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_power"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, coordinator.address)})

    @property
    def available(self) -> bool:
        return super().available and bool((self.coordinator.data or {}).get("available"))

    @property
    def native_value(self) -> int | None:
        return (self.coordinator.data or {}).get("watts")
