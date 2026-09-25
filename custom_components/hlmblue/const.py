"""Constants for the A/C Remote (BLE) integration."""

DOMAIN = "hlmblue"

CONF_ADDRESS = "address"
CONF_PIN = "pin"
DEFAULT_PIN = "0000"
CONF_CONFIGURED = "configured"

# The unit is request/response and drops idle connections; poll on this cadence.
POLL_INTERVAL = 30  # seconds
# hvac_action is "cooling"/"heating" above this power draw, else "idle".
# Measured on a live unit: 19-24 W idle or on the fan alone, 61-91 W while the
# fan runs on after a power-off, and 316 W upwards once the inverter compressor
# is working. 150 W sits in the gap, where 80 W sat inside the fan band and read
# fan run-on as cooling.
RUNNING_WATTS = 150
# How long a power command outranks the unit's own report of DPID 0x01, which is
# what on/off is actually read from. Only the status read that follows a command
# by a fraction of a second needs covering -- it may predate the unit acting --
# and the hold lifts as soon as the report agrees, so one poll is plenty.
POWER_SETTLE = POLL_INTERVAL  # seconds
