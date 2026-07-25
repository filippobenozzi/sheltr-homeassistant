"""Test della logica di polling del coordinator."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from homeassistant.core import HomeAssistant

from .const import STATUS_URL, build_status


def _refresh_calls(mock: AiohttpClientMocker) -> list[str]:
    return [
        call[1].query.get("refresh", "0")
        for call in mock.mock_calls
        if str(call[1]).startswith(STATUS_URL)
    ]


async def test_first_refresh_is_cheap(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_portal: AiohttpClientMocker,
) -> None:
    """Il primo aggiornamento non interroga i moduli: il setup resta rapido."""
    assert _refresh_calls(mock_portal) == ["0"]


async def test_active_poll_follows_interval(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_portal: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Dopo il primo aggiornamento parte il polling attivo dei moduli."""
    mock_portal.clear_requests()
    mock_portal.get(STATUS_URL, json=build_status())

    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert _refresh_calls(mock_portal) == ["1"]

    # Entro l'intervallo di polling attivo (300 s) si torna alla lettura leggera.
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert _refresh_calls(mock_portal) == ["1", "0"]


async def test_active_poll_disabled_by_option(
    hass: HomeAssistant,
    mock_portal: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Con intervallo 0 il polling attivo avviene solo su richiesta."""
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry, options={"scan_interval": 30, "active_poll_interval": 0}
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_portal.clear_requests()
    mock_portal.get(STATUS_URL, json=build_status())

    for _ in range(3):
        freezer.tick(timedelta(seconds=31))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert _refresh_calls(mock_portal) == ["0", "0", "0"]
