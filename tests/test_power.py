"""DPID 0x01 is the unit's on/off state (1 = on); the power draw says whether it
is working. PowerTracker reads the first and infers nothing from the second.

The figures here are real, read off the unit: 19-24 W idle or on the fan alone,
61-91 W while the fan runs on after a power-off, 316-396 W with the inverter
compressor at low output, 645-861 W working hard.
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components" / "hlmblue"))

import pytest  # noqa: E402
from const import POWER_SETTLE, RUNNING_WATTS  # noqa: E402
from power import PowerTracker  # noqa: E402

ON, OFF = 1, 0


@pytest.fixture
def tracker():
    return PowerTracker(RUNNING_WATTS, POWER_SETTLE)


def test_starts_off(tracker):
    assert not tracker.is_on
    assert not tracker.is_running


def test_dp01_is_the_switch_not_the_compressor(tracker):
    """The measurement this module is built on.

    Fan-only mode at 24 W: the compressor cannot be running at that draw, and
    the unit still reports 0x01 = 1. Reading 0x01 as a compressor flag (or
    inferring power from the draw) gets this exactly backwards.
    """
    tracker.report(ON, 24, now=0)
    assert tracker.is_on
    assert not tracker.is_running


def test_idle_at_the_setpoint_is_on_but_not_cooling(tracker):
    tracker.report(ON, 19, now=0)
    assert tracker.is_on
    assert not tracker.is_running


def test_off_is_reported_as_zero(tracker):
    tracker.report(ON, 800, now=0)
    tracker.report(OFF, 19, now=30)
    assert not tracker.is_on


def test_power_draw_alone_never_decides_on_or_off(tracker):
    """A draw with no 0x01 beside it says nothing about the switch."""
    tracker.report(None, 861, now=0)
    assert not tracker.is_on
    assert tracker.is_running


def test_someone_used_the_units_own_remote(tracker):
    tracker.report(ON, 700, now=0)
    assert tracker.is_on
    assert tracker.is_running


def test_off_survives_a_status_read_that_predates_it(tracker):
    """The status query goes out 0.4 s behind the command, so its answer can
    still describe a unit that has not acted yet. Without the hold, that read
    turns the unit straight back on -- the cool -> off bug."""
    tracker.report(ON, 861, now=0)
    tracker.command(False, now=10)

    tracker.report(ON, 861, now=10.4)  # stale: still reports on, still working
    assert not tracker.is_on

    tracker.report(OFF, 82, now=40)  # caught up
    assert not tracker.is_on
    assert not tracker.is_running


def test_spin_down_does_not_turn_it_back_on(tracker):
    """Watts stay high for a moment after the unit switches off, and 81 W is the
    fan alone. Neither may resurrect the entity."""
    tracker.command(False, now=0)
    for offset, watts in enumerate([861, 827, 645, 208, 82, 81]):
        tracker.report(OFF, watts, now=0.4 + offset)
        assert not tracker.is_on, f"turned itself back on at {watts} W"


def test_an_ignored_off_command_gives_up(tracker):
    """Still reporting on once the window closes: the off did not take, and
    saying so beats lying indefinitely."""
    tracker.command(False, now=0)
    tracker.report(ON, 800, now=POWER_SETTLE - 1)
    assert not tracker.is_on

    tracker.report(ON, 800, now=POWER_SETTLE + 1)
    assert tracker.is_on


def test_the_hold_releases_as_soon_as_the_unit_agrees(tracker):
    """Once the unit has confirmed, a change made elsewhere is picked up at once
    rather than waiting out the rest of the window."""
    tracker.command(False, now=0)
    tracker.report(OFF, 19, now=1)
    assert not tracker.is_on

    tracker.report(ON, 19, now=2)
    assert tracker.is_on


def test_a_batch_without_dp01_leaves_the_state_alone(tracker):
    tracker.report(ON, 24, now=0)
    tracker.report(None, 340, now=1)
    assert tracker.is_on
    assert tracker.is_running


def test_low_inverter_output_counts_as_working(tracker):
    tracker.report(ON, 340, now=0)
    assert tracker.is_running


def test_fan_run_on_does_not(tracker):
    tracker.report(ON, 81, now=0)
    assert not tracker.is_running


def test_a_fresh_command_restarts_the_window(tracker):
    tracker.command(False, now=0)
    tracker.command(True, now=POWER_SETTLE - 1)
    assert tracker.is_on

    tracker.report(OFF, 19, now=POWER_SETTLE + 5)
    assert tracker.is_on, "the second command's window should still be open"
