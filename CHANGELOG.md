# Changelog

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
