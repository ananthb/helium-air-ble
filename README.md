# hlmblue

Reverse-engineering notes for the Bluetooth Low Energy interface on **vendor**
air conditioners, sold in India and controlled by the
[the vendor app](https://play.google.com/store/apps/details?id=com.vendor.mobileapp)
app.

The goal is local control with no vendor cloud: a browser-based Web Bluetooth app,
and a Home Assistant integration installable through HACS.

**Status: the protocol is not cracked yet.** The GATT layer is fully mapped and
the device is reachable, but its command framing is still unknown. See
[`docs/protocol.md`](docs/protocol.md) for exactly what is known, what was tried,
and what would settle it. Contributions from other vendor owners are very welcome
— especially packet captures.

## What works today

- Complete GATT service and characteristic map ([`docs/gatt.json`](docs/gatt.json))
- A decoded 158-byte device-information blob, including model and a probable
  default key
- A working method for talking to the AC through an
  [ESPHome Bluetooth proxy](https://esphome.io/components/bluetooth_proxy.html)
  rather than needing a radio in the same room

## What does not work

The unit acknowledges every write at the ATT layer and answers none of them.
Seventeen candidate query framings produced zero bytes on either notify channel.
Nothing short of observing the real app will settle the format — see
[Cracking it](docs/protocol.md#cracking-it).

## Hardware this was captured from

| | |
|---|---|
| advertised name | `HELM__9869` |
| model string | `HELM0000015HMKP1ac` |
| vendor string | `vendor` |
| observed via | ESPHome 2026.7.4 `bluetooth_proxy`, ESP32 |

If your unit reports a different model string, please open an issue with the
output of [`tools/dump_gatt.py`](tools/dump_gatt.py) — knowing whether the
protocol is shared across models is itself useful.

## Licence

GPL-3.0-only. See [`LICENSE`](LICENSE).
