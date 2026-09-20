// Web Bluetooth transport for a broadcast BLE A/C. Plain JS. Emits semantic
// events; takes semantic intents. All wire encoding/decoding lives in codec.js.
//
// Web Bluetooth is Chrome/Edge/Chromium on desktop and Android only, over HTTPS.
// requestDevice() needs a user gesture; reconnecting to an already-granted device
// via getDevices() does not. Known devices persist in localStorage (for names)
// and via the browser's own permission store (for reconnection).

import { frames, decodeNotify, toStatus } from "./codec.js";

const SVC = 0x00a00a;
const C_CMD = "0000b002-0000-1000-8000-00805f9b34fb";
const C_NTF = "0000b003-0000-1000-8000-00805f9b34fb";
const C_IND = "0000b004-0000-1000-8000-00805f9b34fb";
const STORE = "acr.devices.v1";

export class AcRemote {
  constructor(emit) {
    this.emit = emit; // (event) => void
    this.device = null;
    this.cmd = null;
    this.connected = false;
    this.status = { power: false, temp: 24, mode: "cool", fan: "auto", swing: false, room: 0, watts: 0 };
  }

  // ---- persisted device registry ----
  _load() { try { return JSON.parse(localStorage.getItem(STORE)) || {}; } catch { return {}; } }
  _save(s) { try { localStorage.setItem(STORE, JSON.stringify(s)); } catch {} }
  _remember(id, name) {
    const s = this._load();
    s[id] = { name: name || (s[id] && s[id].name) || "A/C", last: Date.now() };
    this._save(s);
  }
  _forget(id) { const s = this._load(); delete s[id]; this._save(s); }

  async listDevices() {
    const stored = this._load();
    let granted = [];
    try { if (navigator.bluetooth && navigator.bluetooth.getDevices) granted = await navigator.bluetooth.getDevices(); } catch {}
    const byId = {};
    for (const [id, v] of Object.entries(stored)) byId[id] = { id, name: v.name || "A/C", available: false, last: v.last || 0 };
    for (const d of granted) {
      const prev = byId[d.id] || {};
      byId[d.id] = { id: d.id, name: d.name || prev.name || "A/C", available: true, last: prev.last || 0 };
    }
    const devices = Object.values(byId).sort((a, b) => b.last - a.last);
    this.emit({ type: "devices", devices, current: this.connected && this.device ? this.device.id : null });
  }

  async addDevice() {
    if (!navigator.bluetooth) {
      this.emit({ type: "error", message: "This browser has no Web Bluetooth. Use Chrome or Edge on desktop or Android." });
      return;
    }
    try {
      this.emit({ type: "state", state: "connecting" });
      const d = await navigator.bluetooth.requestDevice({ filters: [{ namePrefix: "HELM" }], optionalServices: [SVC] });
      await this._open(d);
    } catch (err) {
      this.emit({ type: "error", message: humanize(err) });
      this.emit({ type: "state", state: "disconnected" });
    }
  }

  async connectId(id) {
    if (!navigator.bluetooth || !navigator.bluetooth.getDevices) return this.addDevice();
    try {
      this.emit({ type: "state", state: "connecting" });
      const devs = await navigator.bluetooth.getDevices();
      const d = devs.find((x) => x.id === id);
      if (!d) {
        this.emit({ type: "error", message: "That A/C isn't paired to this browser anymore — add it again." });
        this.emit({ type: "state", state: "disconnected" });
        return this.listDevices();
      }
      await this._open(d);
    } catch (err) {
      this.emit({ type: "error", message: humanize(err) });
      this.emit({ type: "state", state: "disconnected" });
    }
  }

  async _open(device) {
    this.device = device;
    this.connected = false;
    device.addEventListener("gattserverdisconnected", () => {
      this.connected = false;
      this.emit({ type: "state", state: "disconnected" });
      this.listDevices();
    });
    const server = await device.gatt.connect();
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
    this.connected = true;
    this._remember(device.id, device.name);
    this.emit({ type: "state", state: "login", device: device.name || "A/C" });
    this.listDevices();
  }

  forget(id) {
    this._forget(id);
    if (this.device && this.device.id === id) this.disconnect();
    this.listDevices();
  }

  async login(pin) {
    await this._write(frames.login(pin));
    await this._write(frames.statusQuery());
  }

  async setPower(on) { await this._write(frames.setPower(on)); this._poll(); }
  async setTemp(c) { await this._write(frames.setTemp(c)); this._poll(); }
  async setMode(m) { await this._write(frames.setMode(m)); this._poll(); }
  async setFan(f) { await this._write(frames.setFan(f)); this._poll(); }
  async setSwing(on) { await this._write(frames.setSwing(on)); this._poll(); }

  disconnect() {
    try { if (this.device && this.device.gatt.connected) this.device.gatt.disconnect(); } catch (_) {}
    this.connected = false;
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
  if (/cancelled|User cancelled/i.test(m)) return "No A/C selected.";
  if (/GATT/i.test(m)) return "Lost the Bluetooth connection. Try again.";
  return m;
}
