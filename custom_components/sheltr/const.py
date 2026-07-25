"""Costanti dell'integrazione Sheltr Cloud."""

from __future__ import annotations

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "sheltr"
MANUFACTURER: Final = "Sheltr"

PLATFORMS: Final[list[Platform]] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.LIGHT,
    Platform.SENSOR,
]

# Chiavi di configurazione
CONF_INSTANCE_ID: Final = "instance_id"
CONF_ACTIVE_POLL_INTERVAL: Final = "active_poll_interval"
CONF_POLL_AFTER_COMMAND: Final = "poll_after_command"

# Intervalli (secondi)
DEFAULT_SCAN_INTERVAL: Final = 30
MIN_SCAN_INTERVAL: Final = 5
DEFAULT_ACTIVE_POLL_INTERVAL: Final = 300
DEFAULT_POLL_AFTER_COMMAND: Final = False

# Tipi di scheda supportati dal protocollo 1.6
KIND_LIGHT: Final = "light"
KIND_DIMMER: Final = "dimmer"
KIND_SHUTTER: Final = "shutter"
KIND_THERMOSTAT: Final = "thermostat"

# Mappa tipo scheda -> chiave della collezione dentro `rooms[]` di /status
KIND_COLLECTIONS: Final[dict[str, str]] = {
    KIND_LIGHT: "lights",
    KIND_DIMMER: "dimmers",
    KIND_SHUTTER: "shutters",
    KIND_THERMOSTAT: "thermostats",
}

KIND_LABELS: Final[dict[str, str]] = {
    KIND_LIGHT: "Scheda luci",
    KIND_DIMMER: "Scheda dimmer",
    KIND_SHUTTER: "Scheda tapparelle",
    KIND_THERMOSTAT: "Scheda termostato",
}

# Limiti del backend (webapp/app.py)
DIMMER_MAX_LEVEL: Final = 9
THERMOSTAT_MIN_TEMP: Final = 5.0
THERMOSTAT_MAX_TEMP: Final = 30.0
THERMOSTAT_TEMP_STEP: Final = 0.5

MODE_WINTER: Final = "winter"
MODE_SUMMER: Final = "summer"

DEFAULT_ROOM: Final = "Senza stanza"
