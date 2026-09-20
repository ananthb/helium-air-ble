"""Buttons: roll a new random passkey, or reset the A/C to the 0000 default."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AcConfigEntry
from . import protocol as p
from .const import DOMAIN
from .coordinator import AcCoordinator


async def async_setup_entry(hass, entry: AcConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    c = entry.runtime_data
    async_add_entities(
        [
            AcButton(c, entry, "new_passkey", lambda: c.async_set_passkey(p.random_pin())),
            # Reset is a rarely-used recovery action; hide it from the UI by
            # default so it doesn't clutter dashboards (unhide it in the entity
            # settings if you need it).
            AcButton(c, entry, "reset_passkey", c.async_reset_passkey, visible=False),
        ]
    )


class AcButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: AcCoordinator,
        entry: AcConfigEntry,
        key: str,
        action: Callable[[], Awaitable[None]],
        *,
        visible: bool = True,
    ) -> None:
        self._action = action
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_entity_registry_visible_default = visible
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, coordinator.address)})

    async def async_press(self) -> None:
        await self._action()
