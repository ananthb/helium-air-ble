# A/C Remote — web control panel

A [Web Bluetooth](https://developer.mozilla.org/docs/Web/API/Web_Bluetooth_API)
control panel for broadcast BLE air conditioners. Runs entirely in the browser, talks straight to the
AC over BLE — no cloud, no server.

- **Elm** owns the UI, the connection state machine (`src/Main.elm`) and the
  wire codec (`src/Codec.elm`), all pure. The codec matches the repo's Python
  one and [`../proto/vectors.json`](../proto/vectors.json); `elm-test` checks
  both, along with the torn status frames the unit really sends.
- **Plain JS** owns only the transport (`js/ble.js`): Web Bluetooth and the
  persisted device registry. Frames arrive from Elm ready to write, and
  notifications go back undecoded.

Works in Chrome / Edge / Chromium on desktop and Android, over HTTPS, with the
device in Bluetooth range. iOS Safari and Firefox have no Web Bluetooth.

## Build

```
npm install
npm run build     # -> dist/  (elm make + esbuild)
npm test          # the codec suite (elm-test)
```

Cloudflare Pages runs exactly this (`npm ci` + `npm run build`, output `dist/`)
on every push to `main` and deploys it. Nothing is committed but source.

Note: `elm@0.19.2-0` is a real npm release that downloads the 0.19.2 binary on
install; locally you can also build with `nix shell nixpkgs#elmPackages.elm
nixpkgs#esbuild`.
