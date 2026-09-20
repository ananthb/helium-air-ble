# A/C Remote — web control panel

A [Web Bluetooth](https://developer.mozilla.org/docs/Web/API/Web_Bluetooth_API)
control panel for broadcast BLE air conditioners. Runs entirely in the browser, talks straight to the
AC over BLE — no cloud, no server.

- **Elm** owns the UI and the connection state machine (`src/Main.elm`), pure,
  over ports.
- **Plain JS** owns the transport and wire codec (`js/ble.js`, `js/codec.js`) —
  the codec matches the repo's reference tool and
  [`../proto/vectors.json`](../proto/vectors.json).

Works in Chrome / Edge / Chromium on desktop and Android, over HTTPS, with the
device in Bluetooth range. iOS Safari and Firefox have no Web Bluetooth.

## Build

```
npm install
npm run build     # -> dist/  (elm make + esbuild)
```

Cloudflare Pages runs exactly this (`npm ci` + `npm run build`, output `dist/`)
on every push to `main` and deploys it. Nothing is committed but source.

Note: `elm@0.19.2-0` is a real npm release that downloads the 0.19.2 binary on
install; locally you can also build with `nix shell nixpkgs#elmPackages.elm
nixpkgs#esbuild`.
