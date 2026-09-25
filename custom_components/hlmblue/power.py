"""Tracking whether the A/C is on — pure, no Home Assistant imports.

The unit reports no power state. DPID 0x01 and the power draw say only whether
it is *working*, so a unit that is on but idle at its setpoint looks exactly like
one that is off. Running is therefore taken as proof that it is on, and off is
only ever known because we asked for it.

That leaves the trap this module exists to close. The status read a fraction of
a second after "turn off" catches the compressor still spinning down, and
reading that as "running" turned the unit straight back on in Home Assistant:
cool -> off looked like it did nothing, while going via auto or dry first worked,
because by then the compressor had already stopped. So a power command is
believed until the unit's own report agrees with it, or until the settle window
runs out and the command has evidently not taken.
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

        DPID 0x01 reads 1 while the unit is working, and the draw backs it up.
        Either is enough on its own: the DPID is absent from most notifications,
        which carry a single datapoint each.
        """
        self._running = dp_power == 1 or (watts or 0) > self._running_watts
        if now < self._hold_until:
            if self._running == self._on:
                self._hold_until = 0.0  # the unit agrees; watch it again
        elif self._running:
            self._on = True
