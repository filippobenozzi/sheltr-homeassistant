"""Diagnostica scaricabile da Home Assistant, senza il token."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import SheltrConfigEntry
from .const import CONF_TOKEN

TO_REDACT = {CONF_TOKEN}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SheltrConfigEntry
) -> dict[str, Any]:
    """Configurazione (senza token), collegamento in tempo reale e dati letti dal portale."""
    coordinator = entry.runtime_data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "realtime": coordinator.realtime,
        "homes": coordinator.data,
    }
