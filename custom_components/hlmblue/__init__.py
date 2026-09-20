"""The A/C Remote (BLE) integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_ADDRESS, CONF_PIN, DEFAULT_PIN
from .coordinator import AcCoordinator

PLATFORMS = [Platform.CLIMATE, Platform.SENSOR]

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
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AcConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_shutdown()
    return unloaded
