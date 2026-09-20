"""Number platform: the A/C's auto on/off timers (minutes, 0 cancels).

The unit takes OFF_TIMER / ON_TIMER commands but does not report the remaining
time back in its status stream, so these are optimistic: the value shown is the
one last set from Home Assistant.
"""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import UnitOfTime
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AcConfigEntry
from . import protocol as p
from .const import DOMAIN
from .coordinator import AcCoordinator


async def async_setup_entry(hass, entry: AcConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            AcTimerNumber(coordinator, entry, "off_timer", p.frame_off_timer),
            AcTimerNumber(coordinator, entry, "on_timer", p.frame_on_timer),
        ]
    )


class AcTimerNumber(NumberEntity):
    """An auto on/off timer in minutes (0 cancels)."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 0
    _attr_native_max_value = 1440
    _attr_native_step = 30
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(
        self,
        coordinator: AcCoordinator,
        entry: AcConfigEntry,
        key: str,
        frame: Callable[[int], bytes],
    ) -> None:
        self._coordinator = coordinator
        self._frame = frame
        self._value = 0.0
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, coordinator.address)})

    @property
    def native_value(self) -> float:
        return self._value

    async def async_set_native_value(self, value: float) -> None:
        minutes = int(value)
        await self._coordinator.async_command(self._frame(minutes))
        self._value = float(minutes)
        self.async_write_ha_state()
