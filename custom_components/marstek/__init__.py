from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.typing import ConfigType
import voluptuous as vol

from .const import (
    DOMAIN,
    DEFAULT_SCAN_INTERVAL,
    CONF_SCAN_INTERVAL,
    CONF_IP,
    CONF_PORT,
    CONF_DEVICE_ID,
    CONF_LOCAL_IP,
    CONF_LOCAL_PORT,
    DEFAULT_LOCAL_PORT,
    CONF_TIMEOUT,
    DEFAULT_TIMEOUT,
)
from .api import MarstekApiClient
from .coordinator import MarstekCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["sensor", "number", "select", "binary_sensor"]

SERVICE_REFRESH_NOW = "refresh_now"

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    _LOGGER.warning("Marstek integration loading (version 0.6.10)")
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    merged = {**entry.data, **entry.options}
    ip = merged[CONF_IP]
    port = merged[CONF_PORT]
    device_id = merged[CONF_DEVICE_ID]
    scan_seconds = merged.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    timeout = merged.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)

    api = MarstekApiClient(
        ip, port, device_id,
        timeout=timeout,
        local_ip=merged.get(CONF_LOCAL_IP),
        local_port=merged.get(CONF_LOCAL_PORT, merged.get(CONF_PORT, DEFAULT_LOCAL_PORT)),
    )
    _LOGGER.warning("Marstek API attrs: %s", [a for a in dir(api) if not a.startswith("_")])

    coordinator = MarstekCoordinator(hass, api, timedelta(seconds=scan_seconds))
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as exc:
        _LOGGER.warning("Initial refresh failed: %s", exc)

    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
        "ip": ip,
        "device_id": device_id,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _refresh_service(call: ServiceCall):
        await coordinator.async_request_refresh()
    hass.services.async_register(DOMAIN, SERVICE_REFRESH_NOW, _refresh_service)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
