"""Integrazione Home Assistant per Sheltr Cloud."""

from __future__ import annotations

from homeassistant.const import (
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SheltrAuthError, SheltrClient, SheltrError
from .const import CONF_INSTANCE_ID, PLATFORMS
from .coordinator import SheltrConfigEntry, SheltrCoordinator
from .entity import instance_device_info


async def async_setup_entry(hass: HomeAssistant, entry: SheltrConfigEntry) -> bool:
    """Configura una voce: client, coordinator e piattaforme."""
    session = async_get_clientsession(hass, verify_ssl=entry.data.get(CONF_VERIFY_SSL, True))
    client = SheltrClient(
        session,
        entry.data[CONF_URL],
        entry.data[CONF_INSTANCE_ID],
        token=entry.data.get(CONF_TOKEN),
        username=entry.data.get(CONF_USERNAME),
        password=entry.data.get(CONF_PASSWORD),
    )

    try:
        await client.async_ensure_token()
    except SheltrAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except SheltrError as err:
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = SheltrCoordinator(hass, entry, client)
    try:
        await coordinator.async_load_instance()
    except SheltrError as err:
        raise ConfigEntryNotReady(str(err)) from err

    await coordinator.async_config_entry_first_refresh()

    # Registra subito il dispositivo «impianto»: le schede lo referenziano con via_device.
    device_registry.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        **instance_device_info(coordinator),
    )

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SheltrConfigEntry) -> bool:
    """Scarica la voce e le sue piattaforme."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: SheltrConfigEntry) -> None:
    """Ricarica la voce quando cambiano le opzioni."""
    await hass.config_entries.async_reload(entry.entry_id)
