"""BLE connection + status coordinator for the A/C.

Uses Home Assistant's Bluetooth stack, which transparently routes through ESPHome
Bluetooth proxies, so the A/C need not be near the HA host. The unit is
request/response and gated behind a passkey: on connect we subscribe to the
notify stream, send the passkey login, then a status query; thereafter status
arrives as pushed notifications and we poll periodically as a keepalive.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import timedelta

from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import protocol as p
from .const import CONF_PIN, DEFAULT_PIN, DOMAIN, POLL_INTERVAL, POWER_SETTLE, RUNNING_WATTS
from .power import PowerTracker

_LOGGER = logging.getLogger(__name__)


class AcCoordinator(DataUpdateCoordinator[dict]):
    """Owns one BLE connection to one A/C and its decoded status."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, address: str, pin: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {address}",
            update_interval=timedelta(seconds=POLL_INTERVAL),
        )
        self.entry = entry
        self.address = address
        self.pin = pin
        self._client: BleakClientWithServiceCache | None = None
        self._lock = asyncio.Lock()
        self._raw: dict[int, int | None] = {}
        self._power = PowerTracker(RUNNING_WATTS, POWER_SETTLE)

    # ---- connection ----

    async def _ensure_connected(self) -> None:
        async with self._lock:
            if self._client is not None and self._client.is_connected:
                return
            device = bluetooth.async_ble_device_from_address(self.hass, self.address, connectable=True)
            if device is None:
                raise UpdateFailed(f"{self.address} not in range of any Bluetooth adapter/proxy")
            client = await establish_connection(
                BleakClientWithServiceCache, device, self.address, self._on_disconnect
            )
            await client.start_notify(p.CHAR_NOTIFY, self._on_notify)
            try:
                await client.start_notify(p.CHAR_INDICATE, self._on_notify)
            except Exception:  # noqa: BLE001 - indicate char is optional
                pass
            self._client = client
            # Unlock, then ask for a first status report.
            await self._write(p.frame_login(self.pin))
            await asyncio.sleep(1.0)
            await self._write(p.frame_status())

    def _on_disconnect(self, _client) -> None:
        self._client = None
        self.hass.loop.call_soon_threadsafe(self.async_set_updated_data, self._snapshot())

    async def _write(self, frame: bytes) -> None:
        if self._client is None:
            return
        await self._client.write_gatt_char(p.CHAR_CMD, frame, response=False)

    def _on_notify(self, _sender, data: bytearray) -> None:
        dps = p.decode_notify(bytes(data))
        if not dps:
            return
        # A torn frame whose checksum happens to land is still nonsense, so a
        # reading outside the unit's own range is dropped rather than stored,
        # leaving the last good one in place.
        self._raw.update({k: v for k, v in dps.items() if p.plausible(k, v)})
        self._power.report(self._raw.get(p.DP_POWER), self._raw.get(p.DP_POWER_W), time.monotonic())
        self.async_set_updated_data(self._snapshot())

    # ---- data ----

    def _snapshot(self) -> dict:
        r = self._raw
        watts = r.get(p.DP_POWER_W) or 0
        return {
            "available": self._client is not None and self._client.is_connected,
            "power": self._power.is_on,
            "running": self._power.is_running,
            "temp": r.get(p.DP_TEMP),
            "mode": p.STATUS_MODE.get(r.get(p.DP_MODE)),
            "fan": p.FAN_REV.get(r.get(p.DP_FAN)),
            "swing": bool(r.get(p.DP_SWING_V)),
            "swing_h": bool(r.get(p.DP_SWING_H)),
            "room": r.get(p.DP_ROOM_TEMP),
            "watts": watts,
        }

    async def _async_update_data(self) -> dict:
        # Keepalive poll: reconnect if needed and re-request status.
        await self._ensure_connected()
        await self._write(p.frame_status())
        return self._snapshot()

    # ---- commands ----

    async def async_command(self, frame: bytes, *, power: bool | None = None) -> None:
        await self._ensure_connected()
        if power is not None:
            self._power.command(power, time.monotonic())
        await self._write(frame)
        await asyncio.sleep(0.4)
        await self._write(p.frame_status())
        self.async_set_updated_data(self._snapshot())

    async def async_set_passkey(self, new_pin: str) -> None:
        """Change the A/C's passkey (login with the current one, then send the new
        one — the vendor app's order-based flow) and remember it on the entry."""
        await self._ensure_connected()
        await self._write(p.frame_login(new_pin))
        await self._write(p.frame_status())
        self.pin = new_pin
        self.hass.config_entries.async_update_entry(
            self.entry, data={**self.entry.data, CONF_PIN: new_pin}
        )

    async def async_reset_passkey(self) -> None:
        """Reset the A/C to the 0000 default."""
        await self.async_set_passkey(DEFAULT_PIN)

    async def async_shutdown(self) -> None:
        await super().async_shutdown()
        if self._client is not None:
            try:
                await self._client.disconnect()
            except Exception:  # noqa: BLE001
                pass
            self._client = None
