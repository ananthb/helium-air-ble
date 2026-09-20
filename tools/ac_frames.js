#!/usr/bin/env node
// Reference encoder/decoder for the A/C BLE protocol.
// See docs/protocol.md for the wire format and proto/vectors.json for golden frames.

const command_id = { FIRMWARE_UPDATE:100, VFS_UPDATE:101, SAVE_DEVICE_NAME:103,
  USER_ID:105, FACTORY_RESET:109, STATUS_DATA:500, BLE_PASSKEY:600,
  WIFI:700, AC_CTRL:1003 };

// AC command index -> goes in level[0] of an AC_CTRL frame
const AC_CMD = { POWER:0, SPEED:1, TEMP:2, MODE:3, SWING:4, TURBO:5, SLEEP:6,
  TIMER:7, CONDA:8, ECO:9, DISPLAY:10, REMOTE_DIAG:11, COMPRESSOR:12, ODU:13,
  IDU:14, SAVER:15, AD:16, CONVERTIBLE:17, OFF_TIMER:18, ON_TIMER:19, SILENT:20, SWING_H:21 };
const POWER = { ON:0, OFF:1 };
const MODE  = { DRY:0, COOL:1, AUTO:2, FAN:3, HEAT:4, WIND:5, WET:6, CONVERTIBLE:17 };
const FAN   = { auto:0, low:1, medium:2, high:3 };

// CommandPacketBuilder.serialize()  (25-byte header + payload)
function serialize({cmdId, payload=Buffer.alloc(0), seqNum=1, checksum=0,
                    total_level=0, level0=0, params=0}) {
  const len = payload.length;
  const buf = Buffer.alloc(25 + len);
  buf.writeUInt8(0xFF, 0);              // header
  buf.writeUInt16BE(cmdId, 1);          // cmdId
  buf.writeUInt16BE(len, 3);            // len (= payload length)
  buf.writeUInt16BE(seqNum, 5);         // seqNum (app uses 1)
  buf.writeUInt32BE(checksum>>>0, 7);   // checksum (app sends 0)
  buf.writeUInt8(total_level, 11);      // total_level
  const level = Buffer.alloc(5); level[0] = level0;
  level.copy(buf, 12);                  // level[5]
  buf.writeUInt32BE(len>>>0, 17);       // totalSize (= len)
  buf.writeUInt32BE(params>>>0, 21);    // params (0)
  payload.copy(buf, 25);
  return buf;
}
const frame = o => { const b = serialize(o); return { hex:b.toString('hex'), b64:b.toString('base64') }; };

// The app's own senders, verbatim:
const acCommand   = (acCmd, value) => frame({cmdId:command_id.AC_CTRL, total_level:2, level0:acCmd, payload:Buffer.from(value)});
const setPower    = on   => acCommand(AC_CMD.POWER, [on ? POWER.ON : POWER.OFF]);
const setTemp     = t    => acCommand(AC_CMD.TEMP,  [t & 0xFF]);
const setMode     = m    => acCommand(AC_CMD.MODE,  [m]);
const setFanSpeed = s    => acCommand(AC_CMD.SPEED, [s]);
const requestOdu  = ()   => frame({cmdId:command_id.AC_CTRL, total_level:2, level0:AC_CMD.REMOTE_DIAG, payload:Buffer.from([0])});
const statusReq   = ()   => frame({cmdId:command_id.STATUS_DATA, payload:Buffer.alloc(0)});
const passkey     = pin  => { const p = Buffer.from(String(pin),'utf8').subarray(0,4);
  return frame({cmdId:command_id.BLE_PASSKEY, total_level:1, level0:p[0], payload:p}); };

// Incoming 0xB003 notify decoder (status). Frames are ASCII-hex, '55aa'-delimited.
// layout per unit: 55aa <4 bytes> <dpid:1> <type:1> <len:2 BE> <data:len>
function decodeStatus(hex) {
  hex = hex.toLowerCase().replace(/\s+/g,'');
  const out = [];
  for (const seg of hex.split('55aa')) {
    if (seg.length < 20) continue;
    const f = '55aa' + seg;
    const dpid = f.slice(12,14);
    const len  = parseInt(f.slice(16,20),16) * 2;
    const data = f.slice(20, 20+len);
    out.push({ dpid, value: data ? parseInt(data,16) : null, raw:data });
  }
  return out;
}
const DPID_STATUS = { '01':'Power', '02':'Temperature', '04':'Mode', '05':'Fan Speed',
  '19':'Sleep', '1c':'Power draw (W)', '67':'Turbo', '69':'Silent', '6a':'Room Temp',
  '6d':'Display', '6e':'Swing V', '6f':'Swing H', '79':'Passkey ack' };

if (require.main === module) {
  const show = (k,v) => console.log(k.padEnd(22), v.hex, '\n'.padEnd(1), ' b64:', v.b64);
  console.log('# BLE 0xB002 control frames (write, WithoutResponse)\n');
  show('POWER ON',  setPower(true));
  show('POWER OFF', setPower(false));
  show('TEMP 24C',  setTemp(24));
  show('MODE COOL', setMode(MODE.COOL));
  show('MODE AUTO', setMode(MODE.AUTO));
  show('FAN HIGH',  setFanSpeed(FAN.high));
  show('REQ ODU',   requestOdu());
  show('STATUS REQ',statusReq());
  show('PASSKEY 4271', passkey('4271'));
}
module.exports = { command_id, AC_CMD, POWER, MODE, FAN, serialize, frame,
  acCommand, setPower, setTemp, setMode, setFanSpeed, requestOdu, statusReq, passkey,
  decodeStatus, DPID_STATUS };
