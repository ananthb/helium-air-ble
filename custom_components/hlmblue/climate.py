"""Climate platform for the A/C."""

from __future__ import annotations

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    SWING_OFF,
    SWING_VERTICAL,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AcConfigEntry
from . import protocol as p
from .const import DOMAIN
from .coordinator import AcCoordinator

HVAC_TO_MODE = {
    HVACMode.COOL: "cool",
    HVACMode.DRY: "dry",
    HVACMode.FAN_ONLY: "fan",
    HVACMode.AUTO: "auto",
    HVACMode.HEAT: "heat",
}
MODE_TO_HVAC = {v: k for k, v in HVAC_TO_MODE.items()}


async def async_setup_entry(hass, entry: AcConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([AcClimate(entry.runtime_data, entry)])


class AcClimate(CoordinatorEntity[AcCoordinator], ClimateEntity):
    """A broadcast BLE air conditioner as a climate entity."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1.0
    _attr_min_temp = p.TEMP_MIN
    _attr_max_temp = p.TEMP_MAX
    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.COOL,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
        HVACMode.AUTO,
        HVACMode.HEAT,
    ]
    _attr_fan_modes = [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH]
    _attr_swing_modes = [SWING_OFF, SWING_VERTICAL]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator: AcCoordinator, entry: AcConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, coordinator.address)},
            identifiers={(DOMAIN, coordinator.address)},
            name=entry.title,
            manufacturer="He",
            model="BLE A/C",
        )

    @property
    def _d(self) -> dict:
        return self.coordinator.data or {}

    @property
    def available(self) -> bool:
        return super().available and bool(self._d.get("available"))

    @property
    def current_temperature(self) -> float | None:
        return self._d.get("room")

    @property
    def target_temperature(self) -> float | None:
        return self._d.get("temp")

    @property
    def hvac_mode(self) -> HVACMode:
        if not self._d.get("power"):
            return HVACMode.OFF
        return MODE_TO_HVAC.get(self._d.get("mode"), HVACMode.COOL)

    @property
    def hvac_action(self) -> HVACAction:
        if not self._d.get("power"):
            return HVACAction.OFF
        if not self._d.get("running"):
            return HVACAction.IDLE
        mode = self._d.get("mode")
        if mode == "heat":
            return HVACAction.HEATING
        if mode == "fan":
            return HVACAction.FAN
        if mode == "dry":
            return HVACAction.DRYING
        return HVACAction.COOLING

    @property
    def fan_mode(self) -> str | None:
        return self._d.get("fan")

    @property
    def swing_mode(self) -> str:
        return SWING_VERTICAL if self._d.get("swing") else SWING_OFF

    async def async_set_temperature(self, **kwargs) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        await self.coordinator.async_command(p.frame_temp(int(temp)), power=True)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.async_command(p.frame_power(False), power=False)
            return
        await self.coordinator.async_command(p.frame_power(True), power=True)
        if (mode := HVAC_TO_MODE.get(hvac_mode)) is not None:
            await self.coordinator.async_command(p.frame_mode(mode), power=True)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        await self.coordinator.async_command(p.frame_fan(fan_mode))

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        await self.coordinator.async_command(p.frame_swing(swing_mode == SWING_VERTICAL))

    async def async_turn_on(self) -> None:
        await self.coordinator.async_command(p.frame_power(True), power=True)

    async def async_turn_off(self) -> None:
        await self.coordinator.async_command(p.frame_power(False), power=False)
