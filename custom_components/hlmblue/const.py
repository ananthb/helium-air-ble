"""Constants for the A/C Remote (BLE) integration."""

DOMAIN = "hlmblue"

CONF_ADDRESS = "address"
CONF_PIN = "pin"
DEFAULT_PIN = "0000"

# The unit is request/response and drops idle connections; poll on this cadence.
POLL_INTERVAL = 30  # seconds
# hvac_action is "cooling"/"heating" above this power draw, else "idle".
RUNNING_WATTS = 80
