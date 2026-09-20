// Web Bluetooth transport for a broadcast BLE A/C. Plain JS. Emits semantic
// events; takes semantic intents. All wire encoding/decoding lives in codec.js.
//
// Web Bluetooth is Chrome/Edge/Chromium on desktop and Android only, over HTTPS.
// requestDevice() needs a user gesture; reconnecting via getDevices() does not.
// Known A/Cs persist in localStorage (name + passkey) and via the browser's own
// permission store (for reconnection).
//
// Passkey handling: the A/C is unlocked by a BLE_PASSKEY frame. To change the
// passkey we log in with the current one, then send the new one (the vendor app's
// order-based flow). Note this firmware does not strictly enforce the passkey for
// reading status; 0000 always works and is the reset/escape value.

import { frames, decodeNotify, toStatus } from "./codec.js";

const SVC = 0x00a00a;
const C_CMD = "0000b002-0000-1000-8000-00805f9b34fb";
const C_NTF = "0000b003-0000-1000-8000-00805f9b34fb";
const C_IND = "0000b004-0000-1000-8000-00805f9b34fb";
const STORE = "acr.devices.v2";
const DEFAULT_PIN = "0000";

export function randomPin() {
  let n = "0000";
  while (n === "0000") n = String(Math.floor(Math.random() * 10000)).padStart(4, "0");
  return n;
}

export class AcRemote {
  constructor(emit) {
    this.emit = emit; // (event) => void
    this.device = null;
    this.cmd = null;
    this.connected = false;
    this.status = { power: false, temp: 24, mode: "cool", fan: "auto", swing: false, room: 0, watts: 0 };
  }

  // ---- persisted registry: { id: { name, last, pin } } ----
  _load() { try { return JSON.parse(localStorage.getItem(STORE)) || {}; } catch { return {}; } }
  _save(s) { try { localStorage.setItem(STORE, JSON.stringify(s)); } catch {} }
  _entry(id) { return this._load()[id] || {}; }
  _pinFor(id) { return this._entry(id).pin || DEFAULT_PIN; }
  _remember(id, name, pin) {
    const s = this._load();
    const prev = s[id] || {};
    s[id] = { name: name || prev.name || "A/C", last: Date.now(), pin: pin ?? prev.pin ?? DEFAULT_PIN };
    this._save(s);
  }
  _setPin(id, pin) {
    const s = this._load();
    if (s[id]) { s[id].pin = pin; this._save(s); }
  }
  _forget(id) { const s = this._load(); delete s[id]; this._save(s); }

  async listDevices() {
    const stored = this._load();
    let granted = [];
    try { if (navigator.bluetooth && navigator.bluetooth.getDevices) granted = await navigator.bluetooth.getDevices(); } catch {}
    const byId = {};
    for (const [id, v] of Object.entries(stored)) byId[id] = { id, name: v.name || "A/C", pin: v.pin || DEFAULT_PIN, available: false, last: v.last || 0 };
    for (const d of granted) {
      const prev = byId[d.id] || {};
      byId[d.id] = { id: d.id, name: d.name || prev.name || "A/C", pin: prev.pin || this._pinFor(d.id), available: true, last: prev.last || 0 };
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
      const isNew = !this._load()[d.id];
      await this._open(d);
      if (isNew) {
        // Configure a fresh random passkey on first pairing (from the 0000 default).
        const pin = randomPin();
        await this._changePasskey(pin);
        this._setPin(d.id, pin);
        await this.listDevices();
      }
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
    this._remember(device.id, device.name, null);
    // Auto-unlock with the stored passkey, then ask for a status report.
    await this._write(frames.login(this._pinFor(device.id)));
    await this._write(frames.statusQuery());
    this.emit({ type: "state", state: "login", device: device.name || "A/C" });
    this.listDevices();
  }

  // ---- passkey ----
  async _changePasskey(newPin) {
    // Already logged in with the current passkey; send the new one to change it.
    await this._write(frames.login(newPin));
    await this._write(frames.statusQuery());
  }

  async setPasskey(id, pin) {
    if (!this.connected || !this.device || this.device.id !== id) return;
    const next = pin || randomPin();
    await this._changePasskey(next);
    this._setPin(id, next);
    await this.listDevices();
  }

  async removeDevice(id) {
    // Reset the A/C to the 0000 default (if we're connected to it), then forget it.
    if (this.connected && this.device && this.device.id === id) {
      try { await this._changePasskey(DEFAULT_PIN); } catch {}
      this.disconnect();
    }
    this._forget(id);
    await this.listDevices();
  }

  forget(id) { return this.removeDevice(id); }

  async login(pin) {
    if (this.device) this._setPin(this.device.id, pin);
    await this._write(frames.login(pin));
    await this._write(frames.statusQuery());
  }

  async setPower(on) { await this._write(frames.setPower(on)); this._poll(); }
  async setTemp(c) { await this._write(frames.setTemp(c)); this._poll(); }
  async setMode(m) { await this._write(frames.setMode(m)); this._poll(); }
  async setFan(f) { await this._write(frames.setFan(f)); this._poll(); }
  async setSwing(on) { await this._write(frames.setSwing(on)); this._poll(); }
  async setSwingH(on) { await this._write(frames.setSwingH(on)); this._poll(); }
  async setOffTimer(min) { await this._write(frames.setOffTimer(min)); this._poll(); }
  async setOnTimer(min) { await this._write(frames.setOnTimer(min)); this._poll(); }

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
