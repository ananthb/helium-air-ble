"""Tracking whether the A/C is on — pure, no Home Assistant imports.

DPID 0x01 is the unit's own on/off state, **1 = on, 0 = off**. That is the
inverse of the POWER *command*, where ON is 0 — the same trap as the mode map,
which also differs between what the unit takes and what it reports.

Measured, not inferred: with the unit in fan-only mode and drawing 24 W, well
under `running_watts`, it reported 0x01 = 1. The compressor cannot have been
running at that draw, so 0x01 is not a compressor flag. Off at 19 W it reports 0.

So on/off is read straight from the unit, and the power draw is used only to say
whether it is *working* — which is what `hvac_action` wants, and which 0x01
cannot tell you, since a unit idling at its setpoint is still on.

The one thing a command has to survive is the status read that follows it a
fraction of a second later, which may have been taken before the unit acted. So
a command outranks the unit's report until the report agrees with it, or until
the grace window closes and the command has evidently not taken.
"""

from __future__ import annotations


class PowerTracker:
    """Whether the unit is on, and whether it is working."""

    def __init__(self, running_watts: int, settle: float) -> None:
        self._running_watts = running_watts
        self._settle = settle
        self._on = False
        self._running = False
        self._hold_until = 0.0

    @property
    def is_on(self) -> bool:
        return self._on

    @property
    def is_running(self) -> bool:
        return self._running

    def command(self, on: bool, now: float) -> None:
        """Note that we have asked the unit to turn on or off."""
        self._on = on
        self._hold_until = now + self._settle

    def report(self, dp_power: int | None, watts: int | None, now: float) -> None:
        """Fold in one status report.

        Most notifications carry a single datapoint, so `dp_power` is usually
        absent; the on/off state then simply stands.
        """
        self._running = (watts or 0) > self._running_watts
        if dp_power is None:
            return
        reported_on = dp_power == 1
        if now < self._hold_until:
            if reported_on == self._on:
                self._hold_until = 0.0  # the unit agrees; watch it again
        else:
            self._on = reported_on
