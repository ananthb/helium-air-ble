// Web Bluetooth transport for a broadcast BLE A/C. Plain JS, and only transport:
// it moves bytes and keeps the device registry. Every frame it writes is built
// by Elm (src/Codec.elm) and arrives ready to go; every notification goes back
// to Elm undecoded.
//
// Web Bluetooth is Chrome/Edge/Chromium on desktop and Android only, over HTTPS.
// requestDevice() needs a user gesture; reconnecting via getDevices() does not.
// Known A/Cs persist in localStorage (name + passkey) and via the browser's own
// permission store (for reconnection).
//
// Passkey handling: the A/C is unlocked by a BLE_PASSKEY frame. To change the
// passkey we log in with the current one, then send the new one (the vendor app's
// order-based flow). Elm builds both frames; this file only knows which passkey
// belongs to which device. Note this firmware does not strictly enforce the
// passkey for reading status; 0000 always works and is the reset/escape value.

const SVC = 0x00a00a;
const C_CMD = "0000b002-0000-1000-8000-00805f9b34fb";
const C_NTF = "0000b003-0000-1000-8000-00805f9b34fb";
const C_IND = "0000b004-0000-1000-8000-00805f9b34fb";
const STORE = "acr.devices.v2";
const DEFAULT_PIN = "0000";

export class AcRemote {
  constructor(emit) {
    this.emit = emit; // (event) => void
    this.device = null;
    this.cmd = null;
    this.connected = false;
    this.pollFrame = null; // the status-query frame, handed over by Elm at startup
  }

  // Elm hands over the one frame this file sends on its own initiative.
  setPollFrame(bytes) { this.pollFrame = bytes; }

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
      await this._open(d, isNew);
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

  async _open(device, isNew = false) {
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
    // Elm answers this with the unlock frames, then a status query.
    this.emit({ type: "opened", id: device.id, pin: this._pinFor(device.id), isNew });
    this.emit({ type: "state", state: "login", device: device.name || "A/C" });
    this.listDevices();
  }

  // ---- intents ----

  // Write frames Elm has already built, in the order given. `poll` asks for a
  // status query once the unit has had a moment to act on them.
  async write(frames, poll) {
    for (const f of frames) await this._write(f);
    if (poll) this._poll();
  }

  async setPasskey(id, pin, frames) {
    if (!this.connected || !this.device || this.device.id !== id) return;
    await this.write(frames, false);
    this._setPin(id, pin);
    await this.listDevices();
  }

  async removeDevice(id, frames) {
    // Reset the A/C to the 0000 default (if we're connected to it), then forget it.
    if (this.connected && this.device && this.device.id === id) {
      try { await this.write(frames, false); } catch {}
      this.disconnect();
    }
    this._forget(id);
    await this.listDevices();
  }

  disconnect() {
    try { if (this.device && this.device.gatt.connected) this.device.gatt.disconnect(); } catch (_) {}
    this.connected = false;
  }

  async _write(bytes) {
    if (!this.cmd) return;
    const frame = Uint8Array.from(bytes);
    if (this.cmd.writeValueWithoutResponse) await this.cmd.writeValueWithoutResponse(frame);
    else await this.cmd.writeValue(frame);
  }

  _poll() {
    if (!this.pollFrame) return;
    setTimeout(() => this._write(this.pollFrame).catch(() => {}), 400);
  }

  _onNotify(dataView) {
    this.emit({ type: "notify", bytes: Array.from(new Uint8Array(dataView.buffer)) });
  }
}

function humanize(err) {
  const m = String(err && err.message ? err.message : err);
  if (/cancelled|User cancelled/i.test(m)) return "No A/C selected.";
  if (/GATT/i.test(m)) return "Lost the Bluetooth connection. Try again.";
  return m;
}
