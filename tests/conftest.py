"""Fixture comuni ai test dell'integrazione Sheltr."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.sheltr.const import DOMAIN
from homeassistant.core import HomeAssistant

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


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: Any,
) -> Generator[None, None, None]:
    """Consente il caricamento delle integrazioni custom nei test."""
    yield


@pytest.fixture
def mock_portal(aioclient_mock: AiohttpClientMocker) -> AiohttpClientMocker:
    """Portale Sheltr simulato con login, istanza e stato."""
    aioclient_mock.post(LOGIN_URL, json={"ok": True, "token": TOKEN, "expiresAt": None})
    aioclient_mock.get(INSTANCE_URL, json={"instance": INSTANCE})
    aioclient_mock.get(STATUS_URL, json=build_status())
    return aioclient_mock


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Voce di configurazione pronta all'uso."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Casa Demo",
        data=CONFIG_DATA,
        unique_id=f"{BASE_URL}::{INSTANCE_ID}",
    )


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    mock_portal: AiohttpClientMocker,
    config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Configura l'integrazione con il portale simulato."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry
