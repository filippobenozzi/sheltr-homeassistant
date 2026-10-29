"""Test della configurazione da interfaccia."""

from __future__ import annotations

import aiohttp
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.sheltr.const import CONF_TOKEN, CONF_URL, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import BASE_URL, ME, ME_URL, TOKEN


async def test_user_flow_creates_entry(
    hass: HomeAssistant, mock_portal: AiohttpClientMocker
) -> None:
    """Indirizzo senza schema e con la barra finale: si normalizza e si prova il token."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: "cloud.example.com/", CONF_TOKEN: f" {TOKEN} "}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Sheltr (API · Casa Demo)"
    assert result["data"] == {CONF_URL: BASE_URL, CONF_TOKEN: TOKEN}
    assert result["result"].unique_id == f"{BASE_URL}|{ME['id']}"
    # Il token viaggia come Authorization: Bearer.
    assert aioclient_mock_header(mock_portal) == f"Bearer {TOKEN}"


def aioclient_mock_header(mock: AiohttpClientMocker) -> str | None:
    """Intestazione Authorization dell'ultima chiamata."""
    headers = mock.mock_calls[-1][3] or {}
    return headers.get("Authorization")


async def test_user_flow_invalid_token(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Token revocato o inventato: errore sul campo, si resta nel modulo."""
    aioclient_mock.get(ME_URL, status=401, json={"error": "Token non valido"})
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: BASE_URL, CONF_TOKEN: "shltr_sbagliato"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Portale irraggiungibile."""
    aioclient_mock.get(ME_URL, exc=aiohttp.ClientError())
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: BASE_URL, CONF_TOKEN: TOKEN}
    )
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_portal: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """Lo stesso token due volte no."""
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: BASE_URL, CONF_TOKEN: TOKEN}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_replaces_token(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Token rigenerato nel portale: si aggiorna la voce senza rifarla."""
    result = await setup_integration.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: "shltr_nuovo"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert setup_integration.data[CONF_TOKEN] == "shltr_nuovo"
    # La voce si ricarica col token nuovo.
    await hass.async_block_till_done()
