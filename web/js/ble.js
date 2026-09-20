// Web Bluetooth transport for a A/C. Plain JS. Emits semantic events;
// takes semantic intents. All wire encoding/decoding lives in codec.js.
//
// Web Bluetooth is Chrome/Edge/Chromium on desktop and Android only, over HTTPS,
// behind a user gesture. startNotifications() writes the CCCD for us (unlike a
// raw ESPHome-proxy path), so this stays small.

import { frames, decodeNotify, toStatus } from "./codec.js";

const SVC = 0x00a00a;
const C_CMD = "0000b002-0000-1000-8000-00805f9b34fb";
const C_NTF = "0000b003-0000-1000-8000-00805f9b34fb";
const C_IND = "0000b004-0000-1000-8000-00805f9b34fb";

export class AcRemote {
  constructor(emit) {
    this.emit = emit; // (event) => void
    this.device = null;
    this.cmd = null;
    this.status = { power: false, temp: 24, mode: "cool", fan: "auto", room: 0, watts: 0 };
  }

  async connect() {
    if (!navigator.bluetooth) {
      this.emit({ type: "error", message: "This browser has no Web Bluetooth. Use Chrome or Edge." });
      return;
    }
    try {
      this.emit({ type: "state", state: "connecting" });
      this.device = await navigator.bluetooth.requestDevice({
        filters: [{ namePrefix: "HELM" }],
        optionalServices: [SVC],
      });
      this.device.addEventListener("gattserverdisconnected", () => {
        this.emit({ type: "state", state: "disconnected" });
      });
      const server = await this.device.gatt.connect();
      const svc = await server.getPrimaryService(SVC);
      this.cmd = await svc.getCharacteristic(C_CMD);
      const ntf = await svc.getCharacteristic(C_NTF);
      await ntf.startNotifications();
      ntf.addEventListener("characteristicvaluechanged", (e) => this._onNotify(e.target.value));
      try {
        const ind = await svc.getCharacteristic(C_IND);
        await ind.startNotifications();
        ind.addEventListener("characteristicvaluechanged", (e) => this._onNotify(e.target.value));
      } catch (_) { /* no indicate char, fine */ }
      this.emit({ type: "state", state: "login", device: this.device.name || "A/C" });
    } catch (err) {
      this.emit({ type: "error", message: humanize(err) });
      this.emit({ type: "state", state: "disconnected" });
    }
  }

  async login(pin) {
    await this._write(frames.login(pin));
    await this._write(frames.statusQuery());
  }

  async setPower(on) { await this._write(frames.setPower(on)); this._poll(); }
  async setTemp(c) { await this._write(frames.setTemp(c)); this._poll(); }
  async setMode(m) { await this._write(frames.setMode(m)); this._poll(); }
  async setFan(f) { await this._write(frames.setFan(f)); this._poll(); }

  disconnect() {
    try { this.device && this.device.gatt.connected && this.device.gatt.disconnect(); } catch (_) {}
  }

  async _write(frame) {
    if (!this.cmd) return;
    if (this.cmd.writeValueWithoutResponse) await this.cmd.writeValueWithoutResponse(frame);
    else await this.cmd.writeValue(frame);
  }

  _poll() { setTimeout(() => this._write(frames.statusQuery()).catch(() => {}), 400); }

  _onNotify(dataView) {
    const dp = decodeNotify(new Uint8Array(dataView.buffer));
    if (!dp) return;
    this.status = toStatus(dp, this.status);
    this.emit({ type: "status", ...this.status });
  }
}

function humanize(err) {
  const m = String(err && err.message ? err.message : err);
  if (/cancelled|User cancelled/i.test(m)) return "No device selected.";
  if (/GATT/i.test(m)) return "Lost the Bluetooth connection. Try again.";
  return m;
}
