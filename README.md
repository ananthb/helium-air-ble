# hlmblue

Local control of broadcast BLE air conditioners (sold in India, controlled by the
[the vendor app](https://play.google.com/store/apps/details?id=com.vendor.mobileapp)
app) with no vendor cloud — over Bluetooth Low Energy.

The BLE protocol has been **fully reverse-engineered from the app**. From it, two
things get built:

- a **Home Assistant integration**, installable through HACS;
- a **standalone Web Bluetooth web app**.

## Status

- **Protocol — decoded.** Frame format, command set, value encodings, status
  stream, and the passkey handshake are all mapped from the app's own serializer.
  See [`docs/protocol.md`](docs/protocol.md), with a runnable reference codec in
  [`tools/ac_frames.js`](tools/ac_frames.js) and golden frames in
  [`proto/vectors.json`](proto/vectors.json).
- **How it was extracted** — [`docs/the docs`](docs/the docs).
- **Plan & design decisions** — [`docs/architecture.md`](docs/architecture.md)
  (HACS integration over add-on; TypeScript site over Rust/WASM; share the spec +
  test vectors, not a compiled core).
- **Integration / web app — not built yet.** One field datum gates *control*: the
  4-digit **passkey** a given unit expects. Reading status needs no PIN.

## The protocol in one screen

BLE command channel `0xB002` (write), status `0xB003` (notify), service `0xA00A`,
scan by name prefix `HELM`. An AC command is a 25-byte-header frame with
`cmdId = AC_CTRL (1003)`, the command in `level[0]`, and the value in the payload:

```
POWER ON    ff03eb 0001 0001 00000000 02 0000000000 00000001 00000000 00
TEMP 24 °C  ff03eb 0001 0001 00000000 02 0200000000 00000001 00000000 18
MODE COOL   ff03eb 0001 0001 00000000 02 0300000000 00000001 00000000 01
```

Control is gated behind a 4-digit passkey sent right after connecting. Status
comes back as `55aa`-delimited Tuya-style datapoints, including live power draw
(`0x1C`). Full detail in [`docs/protocol.md`](docs/protocol.md).

## Hardware this was captured from

| | |
|---|---|
| advertised name | `HELM__9869` |
| model string | `HELM0000015HMKP1ac` |
| app | `com.vendor.mobileapp` 1.0.1 (React Native / bytecode) |
| observed via | ESPHome `bluetooth_proxy`, ESP32 |

If your unit reports a different model string, please open an issue with the
output of [`tools/dump_gatt.py`](tools/dump_gatt.py) — and, if you can capture it,
the passkey exchange — so we can tell whether the protocol is shared across models.

## Licence

GPL-3.0-only. See [`LICENSE`](LICENSE).
