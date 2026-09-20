// A/C wire codec — the same frames as the reference tool and the
// Python integration, checked against proto/vectors.json.
// Plain JS, no dependencies. This is "the BLE bits" together with ble.js.

export const CMD = { STATUS_DATA: 500, BLE_PASSKEY: 600, AC_CTRL: 1003 };
export const AC = { POWER: 0, SPEED: 1, TEMP: 2, MODE: 3, SWING: 4, OFF_TIMER: 18, ON_TIMER: 19, SWING_H: 21 };
export const POWER = { ON: 0, OFF: 1 };
export const MODE = { dry: 0, cool: 1, auto: 2, fan: 3, heat: 4, wind: 5, wet: 6 };
export const FAN = { auto: 0, low: 1, medium: 2, high: 3 };
// The A/C *reports* mode with a different value map than it takes commands with
// (verified live): status 0=auto, 1=cool, 2=heat, 3=dry, 4=fan.
const STATUS_MODE = { 0: "auto", 1: "cool", 2: "heat", 3: "dry", 4: "fan" };
const FAN_REV = Object.fromEntries(Object.entries(FAN).map(([k, v]) => [v, k]));

// CommandPacketBuilder.serialize(): 25-byte header + payload.
export function serialize(cmdId, payload = new Uint8Array(0), { totalLevel = 0, level0 = 0 } = {}) {
  const len = payload.length;
  const b = new Uint8Array(25 + len);
  const dv = new DataView(b.buffer);
  b[0] = 0xff;
  dv.setUint16(1, cmdId);
  dv.setUint16(3, len);
  dv.setUint16(5, 1); // seqNum
  dv.setUint32(7, 0); // checksum
  b[11] = totalLevel;
  b[12] = level0; // level[0]; level[1..4]=0
  dv.setUint32(17, len); // totalSize
  dv.setUint32(21, 0); // params
  b.set(payload, 25);
  return b;
}

const acFrame = (ac, value) => serialize(CMD.AC_CTRL, new Uint8Array([value & 0xff]), { totalLevel: 2, level0: ac });
const acBytes = (ac, payload) => serialize(CMD.AC_CTRL, payload, { totalLevel: 2, level0: ac });
const u32be = (n) => {
  const b = new Uint8Array(4);
  new DataView(b.buffer).setUint32(0, Math.max(0, n | 0));
  return b;
};

export const frames = {
  login: (pin) => {
    const p = new TextEncoder().encode(String(pin).padStart(4, "0").slice(0, 4));
    return serialize(CMD.BLE_PASSKEY, p, { totalLevel: 1, level0: p[0] });
  },
  statusQuery: () => serialize(CMD.STATUS_DATA),
  setPower: (on) => acFrame(AC.POWER, on ? POWER.ON : POWER.OFF),
  setTemp: (c) => acFrame(AC.TEMP, c),
  setMode: (m) => acFrame(AC.MODE, MODE[m] ?? MODE.cool),
  setFan: (f) => acFrame(AC.SPEED, FAN[f] ?? FAN.auto),
  setSwing: (on) => acFrame(AC.SWING, on ? 1 : 0),
  setSwingH: (on) => acBytes(AC.SWING_H, new Uint8Array([0, on ? 1 : 0])),
  setOffTimer: (min) => acBytes(AC.OFF_TIMER, u32be(min)),
  setOnTimer: (min) => acBytes(AC.ON_TIMER, u32be(min)),
};

// Incoming 0xB003 notify value is ASCII text "Poll:<seq>:<hexframe>" (or Diag:).
// The hexframe is a standard Tuya datapoint frame:
//   55aa | ver | cmd(07) | len(2 BE) | [dpid type len(2 BE) value]... | checksum
export function decodeNotify(bytes) {
  const text = new TextDecoder().decode(bytes).replace(/\0+$/, "");
  const parts = text.split(":");
  if (parts.length < 3 || parts[0] !== "Poll") return null;
  const hex = parts[parts.length - 1];
  const b = hexToBytes(hex);
  if (!b || b.length < 7 || b[0] !== 0x55 || b[1] !== 0xaa) return null;
  const len = (b[4] << 8) | b[5];
  const out = {};
  let i = 6;
  const end = Math.min(6 + len, b.length);
  while (i + 4 <= end) {
    const dpid = b[i];
    const dl = (b[i + 2] << 8) | b[i + 3];
    let v = 0;
    for (let k = 0; k < dl; k++) v = (v << 8) | b[i + 4 + k];
    out[dpid] = v;
    i += 4 + dl;
  }
  return out;
}

// Fold a batch of decoded datapoints into a UI status object.
// 0x01 tracks the compressor/running state (1 = running). 0x1C is watts.
export function toStatus(dp, prev = {}) {
  const s = { ...prev };
  if (0x01 in dp) s.power = dp[0x01] === 1;
  if (0x02 in dp) s.temp = dp[0x02];
  if (0x04 in dp) s.mode = STATUS_MODE[dp[0x04]] ?? String(dp[0x04]);
  if (0x05 in dp) s.fan = FAN_REV[dp[0x05]] ?? String(dp[0x05]);
  if (0x6a in dp) s.room = dp[0x6a];
  if (0x6e in dp) s.swing = dp[0x6e] === 1;
  if (0x6f in dp) s.swing_h = dp[0x6f] === 1;
  if (0x1c in dp) s.watts = dp[0x1c];
  return s;
}

function hexToBytes(hex) {
  if (hex.length % 2) return null;
  const b = new Uint8Array(hex.length / 2);
  for (let i = 0; i < b.length; i++) {
    const n = parseInt(hex.substr(i * 2, 2), 16);
    if (Number.isNaN(n)) return null;
    b[i] = n;
  }
  return b;
}
