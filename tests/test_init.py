"""Test di configurazione, riautenticazione e scaricamento della voce."""

from __future__ import annotations

from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.sheltr.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .const import CONFIG_DATA, INSTANCE, INSTANCE_URL, LOGIN_URL, STATUS_URL, TOKEN


async def test_setup_and_unload(hass: HomeAssistant, setup_integration: MockConfigEntry) -> None:
    """La voce si configura e si scarica senza errori."""
    assert setup_integration.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(setup_integration.entry_id)
    await hass.async_block_till_done()
    assert setup_integration.state is ConfigEntryState.NOT_LOADED


async def test_login_uses_stored_credentials(
    hass: HomeAssistant, mock_portal: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """Senza token memorizzato viene eseguito il login istanza."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    login_calls = [call for call in mock_portal.mock_calls if str(call[1]) == LOGIN_URL]
    assert login_calls
    assert login_calls[0][2] == {"username": "filippo", "password": "segreta"}


async def test_token_is_renewed_on_expiry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Un 401 sullo stato provoca un nuovo login e il ritentativo."""
    aioclient_mock.post(LOGIN_URL, json={"ok": True, "token": TOKEN})
    aioclient_mock.get(INSTANCE_URL, json={"instance": INSTANCE})
    aioclient_mock.get(STATUS_URL, status=401, json={"error": "Sessione scaduta"})

    entry = MockConfigEntry(
        domain=DOMAIN, data={**CONFIG_DATA, "token": "token-scaduto"}, unique_id="x"
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Due login: quello scatenato dal 401 sull'istanza e quello sullo stato.
    login_calls = [call for call in aioclient_mock.mock_calls if str(call[1]) == LOGIN_URL]
    assert login_calls


async def test_auth_failure_starts_reauth(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Token non valido e nessuna credenziale: parte il flusso di riautenticazione."""
    aioclient_mock.get(INSTANCE_URL, status=401, json={"error": "Sessione non valida"})

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "url": CONFIG_DATA["url"],
            "instance_id": CONFIG_DATA["instance_id"],
            "token": "token-non-valido",
        },
        unique_id="y",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert any(flow["context"]["source"] == "reauth" for flow in flows)


async def test_connection_error_retries(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Portale irraggiungibile: la voce va in retry."""
    aioclient_mock.post(LOGIN_URL, exc=TimeoutError())

    entry = MockConfigEntry(domain=DOMAIN, data=CONFIG_DATA, unique_id="z")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
