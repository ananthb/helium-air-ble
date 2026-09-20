# A/C — web control panel

A [Web Bluetooth](https://developer.mozilla.org/docs/Web/API/Web_Bluetooth_API)
control panel for A/Cs. Runs entirely in the browser, talks straight to the
AC over BLE — no cloud, no server.

- **Elm** owns the UI and the connection state machine (`src/Main.elm`), pure,
  over ports.
- **Plain JS** owns the transport and wire codec (`js/ble.js`, `js/codec.js`) —
  the codec matches [`../tools/ac_frames.js`](../tools/ac_frames.js) and
  [`../proto/vectors.json`](../proto/vectors.json).

Works in Chrome / Edge / Chromium on desktop and Android, over HTTPS, with the
device in Bluetooth range. iOS Safari and Firefox have no Web Bluetooth.

## Build

```
npm install
npm run build     # -> dist/  (elm make + esbuild)
```

Or with nix: `nix shell nixpkgs#elmPackages.elm nixpkgs#esbuild`. Elm 0.19.2.
