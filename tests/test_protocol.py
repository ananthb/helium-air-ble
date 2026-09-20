"""The Python codec must reproduce the golden frames in proto/vectors.json,
exactly like the JS codec and tools/ac_frames.js."""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components" / "hlmblue"))

import protocol as p  # noqa: E402

VECTORS = json.loads((ROOT / "proto" / "vectors.json").read_text())["frames"]

BUILDERS = {
    "power_on": lambda: p.frame_power(True),
    "power_off": lambda: p.frame_power(False),
    "temp_24": lambda: p.frame_temp(24),
    "temp_16": lambda: p.frame_temp(16),
    "mode_cool": lambda: p.frame_mode("cool"),
    "mode_auto": lambda: p.frame_mode("auto"),
    "mode_dry": lambda: p.frame_mode("dry"),
    "fan_high": lambda: p.frame_fan("high"),
    "fan_low": lambda: p.frame_fan("low"),
    "status_request": lambda: p.frame_status(),
    "passkey_4271": lambda: p.frame_login("4271"),
}


def test_frames_match_vectors():
    for name, build in BUILDERS.items():
        assert build().hex() == VECTORS[name], f"{name} mismatch"


def test_decode_status():
    # A real 'Poll' notification: 55aa 03 07 len | dp(02) type(02) len(0004) 00000018
    frame = b"Poll:42:55aa0307000802020004000000180000\x00"
    dps = p.decode_notify(frame)
    assert dps.get(p.DP_TEMP) == 0x18  # 24 C setpoint


def test_decode_garbage():
    assert p.decode_notify(b"not a poll") == {}
    assert p.decode_notify(b"Diag:1:") == {}
