# Changelog

## 0.2.5

- Fix wild temperature readings — the A/C sometimes sends a half-written status
  notification with the next one's bytes behind it, and those bytes were being
  read as a temperature. Home Assistant showed target temperatures like 21930 °C
  and room temperatures in the billions. Status frames are now checked against
  their own length and checksum before they are believed, and a reading outside
  the unit's range is discarded instead of replacing a good one.

## 0.2.4

- The Passkey field is now hidden by default too — reach it from the device
  page (Settings → Devices → the A/C) to view or change the passkey.

## 0.2.3

- The "New random passkey" button is now hidden by default too, so neither
  passkey button clutters dashboards — unhide from the entity settings if needed.

## 0.2.2

- The "Reset passkey to 0000" button is now hidden by default so it doesn't
  clutter dashboards — unhide it from the entity settings if you need it.

## 0.2.1

- Fix the swing selector picking the wrong mode. The A/C's swing read-back
  doesn't map cleanly to vertical/horizontal, which skewed the shown selection;
  the selector is now optimistic and reflects exactly what you chose.

## 0.2.0

- Climate: horizontal swing is now supported alongside vertical — the swing
  control offers off, vertical, horizontal and both, and each is sent to the unit.
- New auto-on and auto-off **timers** (in minutes; 0 cancels).
- Adding an A/C generates and sets a random passkey automatically; the passkey
  field on the add screen is optional, for a unit that already has one you know.
