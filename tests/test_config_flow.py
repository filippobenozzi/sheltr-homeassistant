"""Test del flusso di configurazione."""

from __future__ import annotations

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.sheltr.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import (
    BASE_URL,
    CONFIG_DATA,
    INSTANCE,
    INSTANCE_ID,
    INSTANCE_URL,
    LOGIN_URL,
    STATUS_URL,
    TOKEN,
    build_status,
)


async def test_user_flow_with_credentials(
    hass: HomeAssistant, mock_portal: AiohttpClientMocker
) -> None:
    """Username e password creano la voce e ricavano il token."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], CONFIG_DATA)
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Casa Demo"
    assert result["data"]["url"] == BASE_URL
    assert result["data"]["instance_id"] == INSTANCE_ID
    assert result["result"].unique_id == f"{BASE_URL}::{INSTANCE_ID}"


async def test_user_flow_with_token(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Il solo token istanza è sufficiente."""
    aioclient_mock.get(INSTANCE_URL, json={"instance": INSTANCE})
    aioclient_mock.get(STATUS_URL, json=build_status())

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"url": BASE_URL, "instance_id": INSTANCE_ID, "token": TOKEN},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["token"] == TOKEN
    assert "username" not in result["data"]


async def test_user_flow_missing_auth(hass: HomeAssistant) -> None:
    """Senza credenziali né token il form segnala l'errore."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"url": BASE_URL, "instance_id": INSTANCE_ID}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "missing_auth"}


@pytest.mark.parametrize(
    ("status", "expected"),
    [(401, "invalid_auth"), (404, "instance_not_found"), (500, "unknown")],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    status: int,
    expected: str,
) -> None:
    """Gli errori del portale diventano messaggi del form."""
    aioclient_mock.post(LOGIN_URL, status=status, json={"error": "ko"})

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], CONFIG_DATA)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Portale irraggiungibile."""
    aioclient_mock.post(LOGIN_URL, exc=TimeoutError())

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], CONFIG_DATA)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_restricted_instance(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """La vista minimale del portale significa token senza permessi."""
    aioclient_mock.post(LOGIN_URL, json={"ok": True, "token": TOKEN})
    aioclient_mock.get(
        INSTANCE_URL, json={"instance": {**INSTANCE, "restricted": True, "boards": []}}
    )

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], CONFIG_DATA)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_duplicate_entry_aborts(
    hass: HomeAssistant, mock_portal: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """Lo stesso impianto non può essere aggiunto due volte."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], CONFIG_DATA)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow(
    hass: HomeAssistant, mock_portal: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """La riautenticazione aggiorna le credenziali della voce."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"username": "filippo", "password": "nuova"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data["password"] == "nuova"


async def test_options_flow(hass: HomeAssistant, setup_integration: MockConfigEntry) -> None:
    """Le opzioni di polling vengono salvate come interi."""
    result = await hass.config_entries.options.async_init(setup_integration.entry_id)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "scan_interval": 60,
            "active_poll_interval": 0,
            "poll_after_command": True,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert setup_integration.options == {
        "scan_interval": 60,
        "active_poll_interval": 0,
        "poll_after_command": True,
    }
