"""The A/C Remote (BLE) integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import protocol
from .const import CONF_ADDRESS, CONF_CONFIGURED, CONF_PIN, DEFAULT_PIN
from .coordinator import AcCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CLIMATE, Platform.SENSOR, Platform.TEXT, Platform.BUTTON, Platform.NUMBER]

type AcConfigEntry = ConfigEntry[AcCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: AcConfigEntry) -> bool:
    """Set up an A/C from a config entry."""
    coordinator = AcCoordinator(
        hass,
        entry,
        entry.data[CONF_ADDRESS],
        entry.data.get(CONF_PIN, DEFAULT_PIN),
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # First time on the default passkey: generate a random one and configure it,
    # mirroring the web app. Saved on the entry; changeable later via the passkey
    # text entity / buttons. Best-effort — never block setup on it.
    if entry.data.get(CONF_PIN, DEFAULT_PIN) == DEFAULT_PIN and not entry.data.get(CONF_CONFIGURED):
        try:
            await coordinator.async_set_passkey(protocol.random_pin())
        except Exception:  # noqa: BLE001
            _LOGGER.debug("could not auto-configure a passkey for %s", coordinator.address)
        hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_CONFIGURED: True})

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AcConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_shutdown()
    return unloaded
