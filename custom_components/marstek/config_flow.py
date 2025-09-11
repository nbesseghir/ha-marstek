from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    CONF_IP,
    CONF_PORT,
    CONF_DEVICE_ID,
    CONF_SCAN_INTERVAL,
    CONF_LOCAL_IP,
    CONF_LOCAL_PORT,
    CONF_TIMEOUT,
    CONF_RETRIES, DEFAULT_RETRIES,
    CONF_BACKOFF, DEFAULT_BACKOFF,
    CONF_MIN_POWER_DELTA_W, DEFAULT_MIN_POWER_DELTA_W,
    CONF_FAIL_UNAVAILABLE, DEFAULT_FAIL_UNAVAILABLE,
)

DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_IP, description={"label": "IP* (Marstek Battery)"}): str,
    vol.Optional(CONF_PORT, default=30000, description={"label": "Port (default 30000)"}): int,
    vol.Required(CONF_DEVICE_ID, default="0", description={"label": "Device ID* (default 0)"}): str,
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL, description={"label": "Scan Interval (seconds)"}): int,
    vol.Optional(CONF_LOCAL_IP, description={"label": "local_IP Homeassistant"}): str,
    vol.Optional(CONF_LOCAL_PORT, default=30000, description={"label": "local_port Homeassistant (default 30000)"}): int,
    vol.Optional(CONF_TIMEOUT, default=int(DEFAULT_TIMEOUT), description={"label": "Timeout (s)"}): int,
})

class MarstekConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        if user_input is not None:
            user_input[CONF_PORT] = int(user_input[CONF_PORT])
            user_input[CONF_SCAN_INTERVAL] = int(user_input[CONF_SCAN_INTERVAL])
            if user_input.get(CONF_LOCAL_PORT) is not None:
                user_input[CONF_LOCAL_PORT] = int(user_input[CONF_LOCAL_PORT])
            if user_input.get(CONF_TIMEOUT) is not None:
                user_input[CONF_TIMEOUT] = int(user_input[CONF_TIMEOUT])

            unique = f"{user_input[CONF_IP]}_{user_input[CONF_DEVICE_ID]}"
            await self.async_set_unique_id(unique)

            for entry in self._async_current_entries():
                if entry.unique_id == unique:
                    self.hass.config_entries.async_update_entry(entry, data=user_input)
                    await self.hass.config_entries.async_reload(entry.entry_id)
                    return self.async_abort(reason="reconfigured")

            return self.async_create_entry(title=f"Marstek ({user_input[CONF_IP]})", data=user_input)

        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

class MarstekOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self.entry = entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        if user_input is not None:
            options = dict(self.entry.options)
            for key in (CONF_PORT, CONF_SCAN_INTERVAL, CONF_LOCAL_PORT, CONF_TIMEOUT, CONF_RETRIES, CONF_BACKOFF, CONF_MIN_POWER_DELTA_W, CONF_FAIL_UNAVAILABLE):
                if key in user_input and user_input[key] is not None:
                    try:
                        if key in (CONF_RETRIES, CONF_MIN_POWER_DELTA_W):
                            options[key] = int(user_input[key])
                        elif key in (CONF_BACKOFF,):
                            options[key] = float(user_input[key])
                        else:
                            options[key] = int(user_input[key]) if isinstance(user_input[key], (int, float, str)) else user_input[key]
                    except Exception:
                        options[key] = user_input[key]
            if user_input.get(CONF_LOCAL_IP) is not None:
                options[CONF_LOCAL_IP] = user_input[CONF_LOCAL_IP]
            return self.async_create_entry(title="", data=options)

        merged = {**self.entry.data, **self.entry.options}
        schema = vol.Schema({
            vol.Optional(CONF_PORT, default=merged.get(CONF_PORT, 30000), description={"label": "Port"}): int,
            vol.Optional(CONF_SCAN_INTERVAL, default=merged.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL), description={"label": "Scan Interval (seconds)"}): int,
            vol.Optional(CONF_LOCAL_IP, default=merged.get(CONF_LOCAL_IP), description={"label": "local_IP Homeassistant"}): str,
            vol.Optional(CONF_LOCAL_PORT, default=merged.get(CONF_LOCAL_PORT, 30000), description={"label": "local_port Homeassistant"}): int,
            vol.Optional(CONF_TIMEOUT, default=int(merged.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)), description={"label": "Timeout (s)"}): int,
            vol.Optional(CONF_RETRIES, default=int(merged.get(CONF_RETRIES, DEFAULT_RETRIES)), description={"label": "Retries per cycle"}): int,
            vol.Optional(CONF_BACKOFF, default=float(merged.get(CONF_BACKOFF, DEFAULT_BACKOFF)), description={"label": "Backoff (s)"}): float,
            vol.Optional(CONF_MIN_POWER_DELTA_W, default=int(merged.get(CONF_MIN_POWER_DELTA_W, DEFAULT_MIN_POWER_DELTA_W)), description={"label": "Min power delta (W)"}): int,
            vol.Optional(CONF_FAIL_UNAVAILABLE, default=bool(merged.get(CONF_FAIL_UNAVAILABLE, DEFAULT_FAIL_UNAVAILABLE)), description={"label": "Fail unavailable on timeout"}): bool,
        })
        return self.async_show_form(step_id="init", data_schema=schema)

def async_get_options_flow(config_entry):
    return MarstekOptionsFlow(config_entry)
