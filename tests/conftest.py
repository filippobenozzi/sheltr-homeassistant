"""Fixture comuni ai test dell'integrazione Smart Domo Cerebro."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.sheltr.const import CONF_TOKEN, CONF_URL, DOMAIN
from homeassistant.core import HomeAssistant

from .const import BASE_URL, HOME_ID, HOME_URL, HOMES_URL, ME, ME_URL, TOKEN, home


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: Any,
) -> Generator[None, None, None]:
    """Consente il caricamento delle integrazioni custom nei test."""
    yield


@pytest.fixture(autouse=True)
def no_realtime() -> Generator[AsyncMock, None, None]:
    """Niente flusso in tempo reale nei test: gli eventi si mandano a mano."""
    with patch("custom_components.sheltr.api.SheltrClient.listen", new=AsyncMock()) as listen:
        yield listen


@pytest.fixture
def mock_portal(aioclient_mock: AiohttpClientMocker) -> AiohttpClientMocker:
    """Portale con un impianto, visto col token dell'impianto."""
    aioclient_mock.get(ME_URL, json=ME)
    aioclient_mock.get(HOMES_URL, json=[{"id": HOME_ID, "name": "Casa Demo"}])
    aioclient_mock.get(HOME_URL, json=home())
    return aioclient_mock


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Voce di configurazione pronta all'uso."""
    return MockConfigEntry(
        domain=DOMAIN,
        version=2,
        title="Smart Domo Cerebro (API · Casa Demo)",
        data={CONF_URL: BASE_URL, CONF_TOKEN: TOKEN},
        unique_id=f"{BASE_URL}|{ME['id']}",
    )


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    mock_portal: AiohttpClientMocker,
    config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Integrazione configurata e caricata."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry
