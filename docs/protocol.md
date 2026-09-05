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

## What has been tried and does not work

Both CCCDs were verified enabled by descriptor readback — `0100` on `0xB003`
(notify) and `0200` on `0xB004` (indicate). This matters: a generic
`start_notify()` writes `0100`, which never enables an indicate-only
characteristic, so an early negative result there was a false one.

With both streams confirmed live, these 17 payloads were written to `0xB002`:

```
<>            <?>           <STATUS>      <QUERY>       <aaaa>
01 00         01 00 7a 01   7a 01 00 00   aa 00 00      aa 01 00 00
{"cmd":"get"} {"cmd":"status"}            00            01
```

**Every one was acknowledged at the ATT layer. Not one produced a single byte on
`0xB003` or `0xB004`.** ATT acknowledgement only means the write reached the
characteristic, not that the payload parsed — so this rules nothing out except
these exact framings.

Power draw on the AC's metered socket did not move (1.48 W → 1.63 W, both
standby), so none of them was accidentally a valid command either.

The unit also pushes nothing unsolicited: 75 s connected with both streams enabled
produced silence. It is request/response, and no request has been recognised yet.

## Cracking it

The remaining unknown is the framing, and guessing has a search space too large to
brute force. Two approaches that would settle it, both requiring someone with the
app and the unit:

### Android HCI snoop log

Records the real frames the app sends. Better than decompiling the APK, because it
yields bytes that are known to work rather than inferred ones.

1. Settings → About phone → tap **Build number** seven times.
2. Developer options → **Enable Bluetooth HCI snoop log** → Enabled (Full).
3. Toggle Bluetooth off and on so the log starts clean.
4. In the vendor app, run a short deliberate sequence and write down the order:
   power on, wait 10 s, set temperature to exactly 24, set mode to Cool, power off.
5. Developer options → **Bug report**, or `adb bugreport out.zip`. The log is at
   `FS/data/misc/bluetooth/logs/btsnoop_hci.log` inside it.

Line the writes to the command characteristic up against the noted sequence and
the encoding falls out.

### Impersonate the AC

Advertise a clone — same name, same `0xA00A` service, same four characteristics,
serving the `0xB001` blob above — from a Linux box with a BLE adapter, and let the
app connect to it. Every byte the app writes gets logged, with no root and no
developer options.

This has a second benefit: forward those writes over the network to a real AC
elsewhere and relay the responses back, and the app controls a unit it is nowhere
near. That is also the practical answer to "can I use the app remotely", since
Android offers no supported way to tunnel its own Bluetooth stack.

Note the app may do more than read `0xB001` — a bond, or a challenge using the
`aaaa` field. Even then the opening frames are captured, which is the useful part.

## Reaching the unit through an ESPHome proxy

You do not need a radio in the same room. An ESP32 running
[`bluetooth_proxy`](https://esphome.io/components/bluetooth_proxy.html) works as a
remote GATT client via `aioesphomeapi` — this is how everything above was
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
