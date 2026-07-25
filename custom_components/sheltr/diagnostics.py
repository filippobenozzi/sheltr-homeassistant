"""Diagnostica della voce di configurazione Sheltr."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .coordinator import SheltrConfigEntry

TO_REDACT = {CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME, "assignedUserIds"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SheltrConfigEntry
) -> dict[str, Any]:
    """Esporta configurazione e stato correnti, senza credenziali."""
    coordinator = entry.runtime_data
    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "instance": async_redact_data(coordinator.instance, TO_REDACT),
        "data": asdict(coordinator.data) if coordinator.data else None,
    }
