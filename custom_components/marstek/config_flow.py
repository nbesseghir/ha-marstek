from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.core import callback

from .const import (
    DOMAIN,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    CONF_IP,
    CONF_PORT,
    CONF_DEVICE_ID,
    CONF_SCAN_INTERVAL,
    CONF_LOCAL_IP,
    CONF_LOCAL_PORT,
    CONF_TIMEOUT,
    CONF_MIN_POWER_DELTA_W, DEFAULT_MIN_POWER_DELTA_W,
    CONF_MARK_UNAVAILABLE_ON_TIMEOUT, DEFAULT_MARK_UNAVAILABLE_ON_TIMEOUT,
)

DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_IP): str,
    vol.Optional(CONF_PORT, default=30000): int,
    vol.Required(CONF_DEVICE_ID, default="0"): str,
})

class MarstekConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        if user_input is not None:
            await self.async_set_unique_id(f"{user_input[CONF_IP]}_{user_input[CONF_DEVICE_ID]}")
            self._abort_if_unique_id_configured()

            user_input[CONF_PORT] = int(user_input[CONF_PORT])

            data = {
                CONF_IP: user_input[CONF_IP],
                CONF_PORT: user_input[CONF_PORT],
                CONF_DEVICE_ID: user_input[CONF_DEVICE_ID],
            }

            options = {
                CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                CONF_LOCAL_IP: "",
                CONF_LOCAL_PORT: None,
                CONF_TIMEOUT: DEFAULT_TIMEOUT,
            }

            return self.async_create_entry(
                title=f"Marstek ({user_input[CONF_IP]})",
                data=data,
                options=options
            )

        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return MarstekOptionsFlow(config_entry)

class MarstekOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self.entry = entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        if user_input is not None:
            options = dict(self.entry.options)
            options.update({
                CONF_PORT: int(user_input[CONF_PORT]),
                CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                CONF_LOCAL_PORT: int(user_input[CONF_LOCAL_PORT]),
                CONF_TIMEOUT: int(user_input[CONF_TIMEOUT]),
                CONF_MIN_POWER_DELTA_W: int(user_input[CONF_MIN_POWER_DELTA_W]),
                CONF_MARK_UNAVAILABLE_ON_TIMEOUT: user_input[CONF_MARK_UNAVAILABLE_ON_TIMEOUT],
                CONF_LOCAL_IP: user_input[CONF_LOCAL_IP],
            })
            return self.async_create_entry(title="", data=options)

        merged = {**self.entry.data, **self.entry.options}
        schema = vol.Schema({
            vol.Optional(CONF_PORT, default=merged.get(CONF_PORT, DEFAULT_PORT)): int,
            vol.Optional(CONF_SCAN_INTERVAL, default=merged.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)): int,
            vol.Optional(CONF_TIMEOUT, default=int(merged.get(CONF_TIMEOUT, DEFAULT_TIMEOUT))): int,
            vol.Optional(CONF_MIN_POWER_DELTA_W, default=int(merged.get(CONF_MIN_POWER_DELTA_W, DEFAULT_MIN_POWER_DELTA_W))): int,
            vol.Optional(CONF_MARK_UNAVAILABLE_ON_TIMEOUT, default=bool(merged.get(CONF_MARK_UNAVAILABLE_ON_TIMEOUT, DEFAULT_MARK_UNAVAILABLE_ON_TIMEOUT))): bool,
        })
        return self.async_show_form(step_id="init", data_schema=schema)
