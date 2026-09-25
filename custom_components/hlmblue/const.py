"""Constants for the A/C Remote (BLE) integration."""

DOMAIN = "hlmblue"

CONF_ADDRESS = "address"
CONF_PIN = "pin"
DEFAULT_PIN = "0000"
CONF_CONFIGURED = "configured"

# The unit is request/response and drops idle connections; poll on this cadence.
POLL_INTERVAL = 30  # seconds
# hvac_action is "cooling"/"heating" above this power draw, else "idle".
# Measured on a live unit: ~19 W in standby, 61-91 W on the fan alone (including
# the run-on for half a minute after a power-off), and 316 W upwards once the
# inverter compressor is working. 150 W sits in the gap between those last two,
# where 80 W sat inside the fan band and read fan run-on as cooling.
RUNNING_WATTS = 150
# How long the unit is given to act on a power command before its own report is
# believed again. See power.py: a report taken mid spin-down looks like a unit
# that is still running, which is what made cool -> off appear to do nothing.
POWER_SETTLE = 60  # seconds
