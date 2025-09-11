DOMAIN = "marstek"

DEFAULT_PORT = 30000
DEFAULT_SCAN_INTERVAL = 10  # seconds
DEFAULT_LOCAL_PORT = 30000
DEFAULT_TIMEOUT = 5.0

CONF_IP = "ip"
CONF_PORT = "port"
CONF_DEVICE_ID = "device_id"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_LOCAL_IP = "local_ip"
CONF_LOCAL_PORT = "local_port"
CONF_TIMEOUT = "timeout"

# Polling robustness
CONF_RETRIES = "retries"
DEFAULT_RETRIES = 2
CONF_BACKOFF = "backoff"
DEFAULT_BACKOFF = 0.2  # seconds

# Smoothing & availability
CONF_MIN_POWER_DELTA_W = "min_power_delta_w"
DEFAULT_MIN_POWER_DELTA_W = 0

CONF_FAIL_UNAVAILABLE = "fail_unavailable"
DEFAULT_FAIL_UNAVAILABLE = False
