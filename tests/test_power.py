"""The unit never says whether it is on, only whether it is working, so
PowerTracker has to hold a power command until the unit's report catches up.

The watt figures here are real, read off the unit through its own power-draw
datapoint: ~19 W in standby, 61-91 W on the fan alone, 316-396 W with the
inverter compressor at low output, and 645-861 W working hard.
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components" / "hlmblue"))

import pytest  # noqa: E402
from const import POWER_SETTLE, RUNNING_WATTS  # noqa: E402
from power import PowerTracker  # noqa: E402


@pytest.fixture
def tracker():
    return PowerTracker(RUNNING_WATTS, POWER_SETTLE)


def test_starts_off(tracker):
    assert not tracker.is_on
    assert not tracker.is_running


def test_running_unit_is_taken_as_on(tracker):
    """Someone used the A/C's own remote; the draw is the only way we find out."""
    tracker.report(None, 827, now=0)
    assert tracker.is_on
    assert tracker.is_running


def test_off_survives_the_compressor_spinning_down(tracker):
    """The bug: cool -> off appeared to do nothing.

    The status query goes out 0.4 s behind the command, and the compressor is
    still pulling hundreds of watts when the answer comes back.
    """
    tracker.report(None, 861, now=0)
    assert tracker.is_on

    tracker.command(False, now=10)
    for offset, watts in enumerate([861, 827, 645, 208, 82, 81]):
        tracker.report(None, watts, now=10.4 + offset)
        assert not tracker.is_on, f"turned itself back on at {watts} W"

    # Settled, and it stays off across later polls.
    tracker.report(None, 19, now=40)
    tracker.report(None, 19, now=70)
    tracker.report(None, 19, now=100)
    assert not tracker.is_on


def test_fan_run_on_is_not_running(tracker):
    """81 W is the fan alone. Under the old 80 W threshold this read as cooling."""
    tracker.report(None, 81, now=0)
    assert not tracker.is_running
    assert not tracker.is_on


def test_low_inverter_output_is_running(tracker):
    """The compressor sustains ~340 W at low output; that is real cooling."""
    tracker.report(None, 340, now=0)
    assert tracker.is_running
    assert tracker.is_on


def test_an_ignored_off_command_gives_up(tracker):
    """If the unit is still working once the window closes, the off did not take
    and the entity should say so rather than lie indefinitely."""
    tracker.command(False, now=0)
    tracker.report(None, 800, now=POWER_SETTLE - 1)
    assert not tracker.is_on

    tracker.report(None, 800, now=POWER_SETTLE + 1)
    assert tracker.is_on


def test_the_hold_releases_as_soon_as_the_unit_agrees(tracker):
    """Once the unit is seen stopped, a later start is picked up at once rather
    than waiting out the rest of the window."""
    tracker.command(False, now=0)
    tracker.report(None, 19, now=1)  # agreed: off
    assert not tracker.is_on

    tracker.report(None, 700, now=2)  # started again, well inside the window
    assert tracker.is_on


def test_turning_on_holds_through_an_idle_report(tracker):
    """A unit that is on but idle at its setpoint draws no more than the fan, and
    must not be read back as off."""
    tracker.command(True, now=0)
    tracker.report(None, 19, now=1)
    assert tracker.is_on

    tracker.report(None, 19, now=POWER_SETTLE + 10)
    assert tracker.is_on


def test_dp_power_alone_is_enough(tracker):
    """Most notifications carry a single datapoint, so the running flag arrives
    without a watts reading beside it."""
    tracker.report(1, None, now=0)
    assert tracker.is_running
    assert tracker.is_on

    tracker.report(0, None, now=1)
    assert not tracker.is_running


def test_a_fresh_command_restarts_the_window(tracker):
    tracker.command(False, now=0)
    tracker.command(True, now=POWER_SETTLE - 1)
    assert tracker.is_on

    tracker.report(None, 19, now=POWER_SETTLE + 5)
    assert tracker.is_on, "the second command's window should still be open"
