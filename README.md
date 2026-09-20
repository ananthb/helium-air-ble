# hlmblue

Local control of a Bluetooth air conditioner — a Home Assistant integration and a
web app, no vendor cloud. The wire protocol is documented under [`docs/`](docs/).

## Home Assistant

Add this repo to [HACS](https://hacs.xyz) as a custom repository (category
*Integration*), install **He A/C (BLE)**, then add it from Settings → Devices &
Services. It reaches the A/C through an ESPHome Bluetooth proxy.

## Web app

**[hlm.blue](https://hlm.blue)** — a Web Bluetooth remote. Chrome or Edge, with
the A/C in Bluetooth range.

## Licence

GPL-3.0-only. See [`LICENSE`](LICENSE).
