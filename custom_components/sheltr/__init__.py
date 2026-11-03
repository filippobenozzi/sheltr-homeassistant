"""Smart Domo Cerebro: luci, dimmer, tapparelle, termostati, sequenze e ingressi degli impianti."""

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
    coordinator = SheltrCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    coordinator.start_listening()
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: SheltrConfigEntry) -> bool:
    """Versione 1: col portale precedente (ID impianto) si rifà; con indirizzo e token si aggiorna."""
    if entry.version < 2:
        if (
            "instance_id" in entry.data
            or CONF_TOKEN not in entry.data
            or CONF_URL not in entry.data
        ):
            _LOGGER.error(
                "%s: configurazione per il portale Smart Domo Cerebro precedente (ID impianto e credenziali). "
                "Rimuovi l'integrazione e aggiungila di nuovo con l'indirizzo del portale e un token "
                "(impianto → Impostazioni → API dell'impianto)",
                entry.title,
            )
            return False
        hass.config_entries.async_update_entry(entry, version=2)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SheltrConfigEntry) -> bool:
    """Chiude il collegamento in tempo reale e toglie le entità."""
    await entry.runtime_data.stop_listening()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
