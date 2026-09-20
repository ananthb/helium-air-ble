# A/C BLE protocol — what is known

Everything here was observed on one unit (`HELM__9869`, model
`HELM0000015HMKP1ac`) between 2026-08 and 2026-09-05. Where something is inferred
rather than observed, it says so.

## Advertisement

```
02 01 05                            flags: LE Limited Discoverable, BR/EDR not supported
03 03 0A A0                         complete 16-bit service UUIDs: 0xA00A
12 09 "HELM:HELM__9869\x00\x00"     complete local name
```

- Address `E8:8F:8E:01:98:69`, **public** (address type 0), connectable.
- No manufacturer data and no service data. The advertisement carries nothing but
  identity — all state and control lives behind GATT.
- Advertising interval measured around 20 s, so discovery is not instant.
- The local name is `HELM:` followed by the name, then two NUL bytes. The
  `0x2A00` GAP characteristic reports the same name without the `HELM:` prefix.

## GATT map

Machine-readable copy: [`gatt.json`](gatt.json). MTU negotiates to 247.

| Service | Handle | Char | Handle | Properties | Notes |
|---|---|---|---|---|---|
| `0x1801` Generic Attribute | 1 | `0x2A05` | 3 | indicate | Service Changed |
| `0x1800` Generic Access | 5 | `0x2A00` | 7 | read | `HELM__9869` |
| | | `0x2A01` | 9 | read | Appearance, `0000` |
| | | `0x2A04` | 11 | read | Preferred conn params, all zero |
| **`0xA00A`** vendor | 12 | **`0xB001`** | 14 | read | device info blob, below |
| | | **`0xB002`** | 17 | write, write-no-response | **command channel** |
| | | **`0xB003`** | 19 | notify | status stream |
| | | **`0xB004`** | 22 | indicate | second stream, purpose unknown |
| `0x180F` Battery | 24 | `0x2A19` | 26 | read, notify | reads `0x5A` (90) |

`0xB001` has a `0x2901` user description descriptor; `0xB003` and `0xB004` each
have a `0x2902` CCCD, at handles 20 and 23.

The battery service reading 90% on a mains-powered air conditioner is almost
certainly vestigial — a default from whatever module vendor supplied the BLE
stack, not a real measurement.

## The `0xB001` device information blob

158 bytes, fixed layout, null-padded fields:

```
  0  01 00 7a 01 48 65 6c 69 75 6d 00 00 00 00 00 00  ..z.vendor......
 16  00 00 00 00 48 45 4c 4d 30 30 30 30 30 31 35 48  ....HELM0000015H
 32  4d 4b 50 31 61 63 00 00 00 00 00 00 00 00 00 00  MKP1ac..........
 48  00 00 00 00 48 45 4c 4d 5f 5f 39 38 36 39 00 00  ....HELM__9869..
 64  00 00 00 00 00 00 00 00 01 00 00 00 16 00 00 00  ................
 80  00 00 00 00 3c 3e 00 00 00 00 00 00 00 00 00 00  ....<>..........
 96  00 00 00 00 04 00 65 38 38 66 38 65 30 31 39 38  ......e88f8e0198
112  36 39 00 00 00 00 00 00 00 61 61 61 61 00 30 00  69.......aaaa.0.
128  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
144  00 00 00 00 00 00 00 00 00 00 00 00 00 00        ..............
```

| Offset | Size | Content | Reading |
|---|---|---|---|
| 0 | 2 | `01 00` | version or flags |
| 2 | 2 | `7a 01` | unknown; `0x017A` = 378 LE, or firmware 1.122 |
| 4 | 16 | `vendor` | vendor, NUL-padded |
| 20 | 32 | `HELM0000015HMKP1ac` | model. `HMKP1` is plausibly the BLE module part number |
| 52 | 20 | `HELM__9869` | device name, matches `0x2A00` |
| 72 | 4 | `01 00 00 00` | = 1 |
| 76 | 4 | `16 00 00 00` | = 22. **Plausibly a °C setpoint** — unconfirmed |
| 84 | 2 | `3c 3e` | = 60, 62 — or the ASCII pair `<>` |
| 100 | 2 | `04 00` | = 4 |
| 102 | 19 | `e88f8e019869` | own MAC, lowercase hex ASCII |
| 121 | 4 | `aaaa` | **probable default key or PIN** |
| 126 | 1 | `0` (0x30) | ASCII digit |

Two fields are worth singling out. `aaaa` is a classic factory-default pairing
key, and its position right after the MAC is where a credential usually sits. And
the literal ASCII `<>` at offset 84 hints that frames may be angle-bracket
delimited — though probing that (below) produced nothing.

Whether offsets 72–85 are live state or a static config copy is **untested**. The
cheapest experiment anyone with physical access can run: read `0xB001`, change the
temperature with the IR remote, read it again, and diff. If those bytes track the
unit, there is a read path even before the command format is known.


## The protocol (decoded from the app)

Everything below was transcribed from the **the vendor app** app itself —
`com.vendor.mobileapp` 1.0.1, a React Native / Expo build whose logic ships as a
bytecode bytecode bundle. See [`the docs`](the docs) for how to reproduce
the extraction; the exact function names cited here are the app's own.

The app speaks the **same command vocabulary over two transports**:

- **BLE** — GATT writes to `0xB002`, notifications on `0xB003`. This is the local
  path and the one this project targets.
- **Cloud** — AWS IoT MQTT (the app ships `AWSiOT.p12` + `AmazonRootCA1.pem`).
  This is how the app does *remote* control once the AC is Wi-Fi provisioned
  (`command_id.WIFI = 700`). Out of scope here, but it explains how the app shows
  and controls a unit you are nowhere near.

### The BLE frame

Every BLE write is one `CommandPacketBuilder.serialize()` structure — a fixed
25-byte header followed by a variable payload, written to `0xB002` as the raw
bytes (the app base64-encodes them only because `react-native-ble-plx` takes
base64; over a GATT write the bytes are what land).

```
off  size  field         encoding   notes
 0    1    header        u8         always 0xFF
 1    2    cmdId         u16 BE     see command_id
 3    2    len           u16 BE     payload length
 5    2    seqNum        u16 BE     app always sends 1
 7    4    checksum      u32 BE     app always sends 0 (not validated by the unit)
11    1    total_level   u8         2 for AC control, 1 for passkey
12    5    level         bytes      level[0] carries the command / dpid; rest 0
17    4    totalSize     u32 BE     = payload length
21    4    params        u32 BE     0
25    …    payload       bytes      value bytes
```

`command_id` (from the app's map):

| name | value | | name | value |
|---|---|---|---|---|
| `FIRMWARE_UPDATE` | 100 | | `STATUS_DATA` | 500 |
| `VFS_UPDATE` | 101 | | `BLE_PASSKEY` | 600 |
| `SAVE_DEVICE_NAME` | 103 | | `WIFI` | 700 |
| `USER_ID` | 105 | | **`AC_CTRL`** | **1003** (`0x03EB`) |
| `FACTORY_RESET` | 109 | | | |

### AC control

An AC command is an `AC_CTRL` (1003) frame with `total_level = 2`, the command in
`level[0]`, and the value in the payload. This is exactly what the app's
`sendACCommand(cmd, valueBytes)` does, and the typed setters (`setPower`,
`setTemperature`, `setMode`, `setFanSpeed`, `setSwing`) are thin wrappers over it.

`level[0]` — the command index:

| cmd | `level[0]` | payload | cmd | `level[0]` | payload |
|---|---|---|---|---|---|
| POWER | 0 | `[on?0:1]` | DISPLAY | 10 | `[on?0:1]` |
| SPEED (fan) | 1 | `[0-3]` | REMOTE_DIAG | 11 | `[0]` |
| TEMP | 2 | `[°C]` | COMPRESSOR | 12 | |
| MODE | 3 | `[mode]` | ODU | 13 | |
| SWING (V) | 4 | `[on?..]` | IDU | 14 | |
| TURBO | 5 | | CONVERTIBLE | 17 | `[val]` |
| SLEEP | 6 | | OFF_TIMER | 18 | `[minBE]` |
| TIMER | 7 | | ON_TIMER | 19 | `[minBE]` |
| CONDA | 8 | | SILENT | 20 | `[on?1:0]` |
| ECO | 9 | | SWING_H | 21 | `[0,on?1:0]` |

Value encodings:

- **power** — `ON = 0`, `OFF = 1` (`AC_CMD_ON`/`AC_CMD_OFF`; note ON is 0).
- **mode** — `DRY 0 · COOL 1 · AUTO 2 · FAN 3 · HEAT 4 · WIND 5 · WET 6 · CONVERTIBLE 17`.
- **fan** — `auto 0 · low 1 · medium 2 · high 3`.
- **temperature** — one byte of °C.

Worked frames (hex, byte-for-byte from the app's serializer; the full set is in
[`../proto/vectors.json`](../proto/vectors.json)):

```
POWER ON    ff03eb 0001 0001 00000000 02 0000000000 00000001 00000000 00
POWER OFF   ff03eb 0001 0001 00000000 02 0000000000 00000001 00000000 01
TEMP 24 °C  ff03eb 0001 0001 00000000 02 0200000000 00000001 00000000 18
MODE COOL   ff03eb 0001 0001 00000000 02 0300000000 00000001 00000000 01
FAN HIGH    ff03eb 0001 0001 00000000 02 0100000000 00000001 00000000 03
```

(Spaces added for reading only.) A reference encoder/decoder is in
[`../tools/ac_frames.js`](../tools/ac_frames.js).

### Status: the `0xB003` notify stream  (verified live)

Status was captured from a live unit through an ESPHome proxy — see
[`../tools/read_status.py`](../tools/read_status.py). Two things the app's code
did not make obvious, both of which cost the earlier "the unit answers nothing"
conclusion:

- **The CCCDs must be written explicitly.** Enabling notifications through a
  generic `start_notify` did *not* enable them here; writing `0x0100` to the
  `0xB003` CCCD (handle 20) and `0x0200` to the `0xB004` CCCD (handle 23) does.
  Until then the unit streams nothing, which is exactly why 75 s of an earlier
  session sat silent.
- **The stream is poked by a write.** After the CCCDs are live, a write to
  `0xB002` (a `STATUS_DATA` request works) triggers the unit to dump its state.

Each notification's **value is ASCII text**, not raw bytes:

```
Poll:1160:55aa03070005 01 01 0001 00 11
Diag:1171:->100149c4 1
```

`Poll:<seq>:<hexframe>` carries state; `Diag:<seq>:…` carries diagnostics. The
`<hexframe>` is a **standard Tuya datapoint frame**:

```
55aa            header
03              version
07              command (0x07 = status report)
00 XX           length of the body, 2 bytes BE
  <dp unit>…    one or more datapoints
XX              checksum (sum of the preceding bytes, mod 256)
```

Each datapoint unit is `dpid(1) · type(1) · len(2 BE) · value(len)` — Tuya's
`0x01` bool, `0x02` 4-byte int, `0x04` enum. DPIDs seen on a live unit:

| dpid | meaning | dpid | meaning |
|---|---|---|---|
| `0x01` | power (`0`=on, `1`=off) | `0x69` | silent |
| `0x02` | temperature setpoint °C | `0x6A` | room temperature °C |
| `0x04` | mode (enum, as above) | `0x6B` | coil temp *(inferred)* |
| `0x05` | fan speed (enum) | `0x6D` | display |
| `0x08` | eco *(inferred)* | `0x6E` | swing vertical |
| `0x19` | sleep | `0x6F` | swing horizontal |
| `0x1A` | health/ionizer *(inferred)* | `0x73` | defrost *(inferred)* |
| `0x1C` | **power draw (W)** | `0x75` | error/fault *(inferred)* |
| `0x67` | turbo | `0x79` | passkey ack |

A live read while the unit was running returned: power **on**, mode **cool**,
setpoint **22 °C**, fan **auto**, room **31 °C**, display on, swing-H on. Reading
status required **no PIN** — the passkey gate is on control, not on observation.

### The passkey handshake — why blind writes did nothing

The AC gates control behind a **4-digit passkey**. After connecting, the app calls
`sendLoginBlePasskey`: a `BLE_PASSKEY` (600) frame, `total_level = 1`, payload =
the four ASCII digits, `level[0]` = the first digit's byte. The unit answers on
`0xB003` with **dpid `0x79`** (`passkeyAck`), and only then are `AC_CTRL` commands
honoured. The PIN is "any 4 digits except `0000`", stored by the app under
`@vendor_passkey_<deviceId>`. The **factory default is `0000`** — a never-paired
or unpaired unit accepts it, and the app's unpair flow "clears passkey and name
from both this phone and the unit", returning it to `0000`. See
[getting a PIN](architecture.md#getting-a-pin).

This resolves the earlier mystery. The seventeen framings tried before were ATT-
acknowledged and silently ignored because **no passkey login preceded them** —
and because none matched the real `AC_CTRL` layout above. Both problems are now
fixed on paper; the open item is obtaining the actual PIN a given unit expects.

## Status verified; control not yet

The read path above is confirmed against a live unit through the ESPHome proxy.
Control frames (`docs`/[`../tools/ac_frames.js`](../tools/ac_frames.js))
are byte-derived from the app but have **not** been written to a physical AC —
that turns the compressor on/off and needs the unit's passkey. The safe, already-
done step is the read; the next is a single `AC_CTRL` write behind a passkey
login, confirmed via the `0x1C` power-draw datapoint and the metered socket.

## Reaching the unit through an ESPHome proxy

You do not need a radio in the same room. An ESP32 running
[`bluetooth_proxy`](https://esphome.io/components/bluetooth_proxy.html) works as a
remote GATT client via `aioesphomeapi` — this is how the GATT map above was
captured. See [`../tools/dump_gatt.py`](../tools/dump_gatt.py).

Two traps cost real time, and neither is documented upstream:

**The ESP routes `BluetoothDeviceConnectionResponse` only to the API connection
that subscribed to advertisements.** Call
`subscribe_bluetooth_le_raw_advertisements()` before `bluetooth_device_connect()`.
Skip it and the ESP will open the connection perfectly — its own log says
`Connection open` and `Service discovery complete` — while your client waits out
its timeout, because the response went to whichever client subscribed first,
usually Home Assistant.

**`feature_flags` is not read from `device_info()`.** Pass
`info.bluetooth_proxy_feature_flags` into `bluetooth_device_connect()` explicitly,
or it defaults to 0 and the call raises `ValueError` claiming the device is too
old to support remote caching.

One more, operational rather than protocol: taking that advertisement
subscription takes BLE proxying away from Home Assistant, and it does not always
hand back. Observed once leaving the scanner stuck at `scanning: false` with
every proxied device unavailable until the ESPHome config entry was reloaded.
Keep such sessions short and check afterwards.
