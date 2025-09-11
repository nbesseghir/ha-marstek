from __future__ import annotations
from typing import Any
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN

async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    coord = data.get("coordinator")
    return {
        "entry": {"data": entry.data, "options": entry.options},
        "last_payload": coord.data if coord else None,
    }
