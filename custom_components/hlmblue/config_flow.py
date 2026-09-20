"""Config flow for A/C Remote (BLE)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import CONF_ADDRESS, CONF_PIN, DEFAULT_PIN, DOMAIN
from .protocol import NAME_PREFIX


class AcConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for an A/C."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered: dict[str, str] = {}  # address -> name
        self._address: str | None = None
        self._name: str | None = None

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a device discovered over Bluetooth."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._address = discovery_info.address
        self._name = discovery_info.name or discovery_info.address
        self.context["title_placeholders"] = {"name": self._name}
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a discovered device and take its passkey."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._name or self._address,
                data={CONF_ADDRESS: self._address, CONF_PIN: user_input[CONF_PIN]},
            )
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({vol.Required(CONF_PIN, default=DEFAULT_PIN): str}),
            description_placeholders={"name": self._name or self._address or ""},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick from discovered A/Cs (or none found)."""
        if user_input is not None:
            self._address = user_input[CONF_ADDRESS]
            self._name = self._discovered.get(self._address, self._address)
            await self.async_set_unique_id(self._address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return await self.async_step_confirm()

        current = self._async_current_ids()
        for info in async_discovered_service_info(self.hass, connectable=True):
            if info.address in current:
                continue
            if (info.name or "").startswith(NAME_PREFIX):
                self._discovered[info.address] = info.name or info.address

        if not self._discovered:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDRESS): vol.In(self._discovered)}
            ),
        )
