"""Test di avvio, chiusura e migrazione."""

from __future__ import annotations

from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.sheltr.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .const import HOMES_URL, ME_URL


async def test_setup_and_unload(hass: HomeAssistant, setup_integration: MockConfigEntry) -> None:
    """Si carica, apre il tempo reale e si chiude."""
    assert setup_integration.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(setup_integration.entry_id)
    await hass.async_block_till_done()
    assert setup_integration.state is ConfigEntryState.NOT_LOADED


async def test_listens_for_realtime(
    hass: HomeAssistant, setup_integration: MockConfigEntry, no_realtime
) -> None:
    """Dopo la prima lettura parte l'ascolto degli impianti letti."""
    no_realtime.assert_called_once()
    assert no_realtime.call_args.args[0] == ["casa1"]


async def test_revoked_token_asks_for_a_new_one(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """Token disattivato nel portale: 401 e richiesta di un token nuovo."""
    aioclient_mock.get(ME_URL, status=401, json={"error": "Token non valido"})
    aioclient_mock.get(HOMES_URL, status=401, json={"error": "Token non valido"})
    config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert [flow["context"]["source"] for flow in flows] == ["reauth"]


async def test_version_1_entry_is_not_migrated(hass: HomeAssistant) -> None:
    """Le voci del plugin 1.x (portale precedente) vanno rifatte: niente conversione."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        title="Casa vecchia",
        data={"url": "http://192.168.1.10:8080", "instance_id": "casa-demo", "token": "vecchio"},
    )
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.MIGRATION_ERROR
