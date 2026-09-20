# Changelog

## 0.1.1

- Adding an A/C no longer prompts for a passkey by default — a random one is
  generated and set on the unit automatically, matching the web app. The passkey
  field is now optional, for the case where an A/C already has one you know.

## 0.1.0

First release.

- Control a broadcast BLE air conditioner from Home Assistant as a `climate`
  entity — power, mode, target temperature, fan and swing — with a power-draw
  sensor. It works through an ESPHome Bluetooth proxy, so the A/C need not be
  near the Home Assistant host.
- Passkey handling: a random passkey is configured on the A/C and saved with it
  when you add the unit. A *Passkey* field reveals or changes it, and buttons
  roll a new random passkey or reset it to 0000.
