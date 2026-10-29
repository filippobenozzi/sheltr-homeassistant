"""Sheltr Cloud: luci, dimmer, tapparelle, termostati, sequenze e ingressi degli impianti Sheltr."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SheltrClient
from .const import CONF_TOKEN, CONF_URL, PLATFORMS
from .coordinator import SheltrCoordinator

_LOGGER = logging.getLogger(__name__)

type SheltrConfigEntry = ConfigEntry[SheltrCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: SheltrConfigEntry) -> bool:
    """Legge gli impianti del token, crea le entità e ascolta gli aggiornamenti."""
    client = SheltrClient(
        async_get_clientsession(hass), entry.data[CONF_URL], entry.data[CONF_TOKEN]
    )
    coordinator = SheltrCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    coordinator.start_listening()
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: SheltrConfigEntry) -> bool:
    """Le voci della versione 1 (portale Sheltr precedente) non si convertono."""
    if entry.version < 2:
        _LOGGER.error(
            "%s: configurazione per il portale Sheltr precedente (ID impianto e credenziali). "
            "Rimuovi l'integrazione e aggiungila di nuovo con l'indirizzo del portale e un token "
            "(impianto → Impostazioni → API dell'impianto)",
            entry.title,
        )
        return False
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SheltrConfigEntry) -> bool:
    """Chiude il collegamento in tempo reale e toglie le entità."""
    await entry.runtime_data.stop_listening()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
