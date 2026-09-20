"""Wire codec for the broadcast BLE A/C — pure, no Home Assistant imports.

Mirrors web/js/codec.js and tools/ac_frames.js, and is checked against
proto/vectors.json by the tests. See docs/protocol.md for the format:

* Commands are a 25-byte header + payload written to the command characteristic.
* Status arrives on the notify characteristic as ASCII text "Poll:<seq>:<hex>",
  where <hex> is a Tuya datapoint frame (55aa | ver | cmd | len | dp-units | crc).
"""

from __future__ import annotations

# GATT
SERVICE_UUID = "0000a00a-0000-1000-8000-00805f9b34fb"
CHAR_CMD = "0000b002-0000-1000-8000-00805f9b34fb"
CHAR_NOTIFY = "0000b003-0000-1000-8000-00805f9b34fb"
CHAR_INDICATE = "0000b004-0000-1000-8000-00805f9b34fb"
NAME_PREFIX = "HELM"

# command_id
CMD_STATUS_DATA = 500
CMD_BLE_PASSKEY = 600
CMD_AC_CTRL = 1003

# AC command index (goes in level[0] of an AC_CTRL frame)
AC_POWER = 0
AC_SPEED = 1
AC_TEMP = 2
AC_MODE = 3
AC_SWING = 4

POWER_ON = 0
POWER_OFF = 1
MODE = {"dry": 0, "cool": 1, "auto": 2, "fan": 3, "heat": 4, "wind": 5, "wet": 6}
# The A/C reports mode with a different value map than it takes commands with
# (verified live): status 0=auto, 1=cool, 2=heat, 3=dry, 4=fan.
STATUS_MODE = {0: "auto", 1: "cool", 2: "heat", 3: "dry", 4: "fan"}
FAN = {"auto": 0, "low": 1, "medium": 2, "high": 3}
FAN_REV = {v: k for k, v in FAN.items()}

# status DPIDs
DP_POWER = 0x01
DP_TEMP = 0x02
DP_MODE = 0x04
DP_FAN = 0x05
DP_POWER_W = 0x1C
DP_SWING_V = 0x6E
DP_ROOM_TEMP = 0x6A
DP_PASSKEY_ACK = 0x79

TEMP_MIN = 16
TEMP_MAX = 30


def serialize(cmd_id: int, payload: bytes = b"", *, total_level: int = 0, level0: int = 0) -> bytes:
    """CommandPacketBuilder.serialize(): 25-byte header + payload."""
    length = len(payload)
    buf = bytearray(25 + length)
    buf[0] = 0xFF
    buf[1:3] = cmd_id.to_bytes(2, "big")
    buf[3:5] = length.to_bytes(2, "big")
    buf[5:7] = (1).to_bytes(2, "big")  # seqNum
    buf[11] = total_level
    buf[12] = level0  # level[0]; level[1..4] and checksum/params stay zero
    buf[17:21] = length.to_bytes(4, "big")  # totalSize
    buf[25:] = payload
    return bytes(buf)


def _ac(ac_cmd: int, value: int) -> bytes:
    return serialize(CMD_AC_CTRL, bytes([value & 0xFF]), total_level=2, level0=ac_cmd)


def frame_login(pin: str) -> bytes:
    p = str(pin).zfill(4)[:4].encode("ascii")
    return serialize(CMD_BLE_PASSKEY, p, total_level=1, level0=p[0])


def frame_status() -> bytes:
    return serialize(CMD_STATUS_DATA)


def frame_power(on: bool) -> bytes:
    return _ac(AC_POWER, POWER_ON if on else POWER_OFF)


def frame_temp(celsius: int) -> bytes:
    return _ac(AC_TEMP, int(celsius))


def frame_mode(mode: str) -> bytes:
    return _ac(AC_MODE, MODE.get(mode, MODE["cool"]))


def frame_fan(fan: str) -> bytes:
    return _ac(AC_SPEED, FAN.get(fan, FAN["auto"]))


def frame_swing(on: bool) -> bytes:
    return _ac(AC_SWING, 1 if on else 0)


def decode_notify(raw: bytes) -> dict[int, int | None]:
    """Decode one 0xB003 notification into {dpid: value}.

    The value is ASCII text "Poll:<seq>:<hexframe>" (or "Diag:..."). The hexframe
    is a Tuya datapoint frame. Returns an empty dict for anything unrecognised.
    """
    text = raw.decode("ascii", "replace").rstrip("\x00")
    parts = text.split(":")
    if len(parts) < 3 or parts[0] != "Poll":
        return {}
    try:
        b = bytes.fromhex(parts[-1])
    except ValueError:
        return {}
    if len(b) < 7 or b[0] != 0x55 or b[1] != 0xAA:
        return {}
    length = (b[4] << 8) | b[5]
    out: dict[int, int | None] = {}
    i = 6
    end = min(6 + length, len(b))
    while i + 4 <= end:
        dpid = b[i]
        dlen = (b[i + 2] << 8) | b[i + 3]
        val = b[i + 4 : i + 4 + dlen]
        out[dpid] = int.from_bytes(val, "big") if val else None
        i += 4 + dlen
    return out


def random_pin() -> str:
    """A random 4-digit passkey, never 0000 (which the app forbids as the default)."""
    import secrets

    while True:
        n = f"{secrets.randbelow(10000):04d}"
        if n != "0000":
            return n
