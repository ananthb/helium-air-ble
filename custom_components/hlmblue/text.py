"""Text platform: view and set the A/C's passkey."""

from __future__ import annotations

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AcConfigEntry
from .const import DOMAIN
from .coordinator import AcCoordinator


async def async_setup_entry(hass, entry: AcConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([AcPasskeyText(entry.runtime_data, entry)])


class AcPasskeyText(TextEntity):
    """The A/C's 4-digit passkey — reveal it (password field) or set a new one."""

    _attr_has_entity_name = True
    _attr_translation_key = "passkey"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = TextMode.PASSWORD
    _attr_native_min = 4
    _attr_native_max = 4
    _attr_pattern = r"\d{4}"

    def __init__(self, coordinator: AcCoordinator, entry: AcConfigEntry) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_passkey"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, coordinator.address)})

    @property
    def native_value(self) -> str:
        return self._coordinator.pin

    async def async_set_value(self, value: str) -> None:
        await self._coordinator.async_set_passkey(value)
        self.async_write_ha_state()
