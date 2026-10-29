"""Test degli aggiornamenti in tempo reale."""

from __future__ import annotations

from unittest.mock import MagicMock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sheltr.api import SheltrClient
from custom_components.sheltr.const import DOMAIN
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import EMPTY_STATE


def light_id(hass: HomeAssistant) -> str:
    """La luce "Lampadario"."""
    found = er.async_get(hass).async_get_entity_id(LIGHT_DOMAIN, DOMAIN, "dr154-channels-b1-c1")
    assert found is not None
    return found


async def test_state_and_device_events(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Un evento "state" cambia lo stato; un gateway offline rende le entità non disponibili."""
    coordinator = setup_integration.runtime_data
    coordinator.handle_event(
        "state", {"channels": [{"channelId": 11, "state": {**EMPTY_STATE, "isOn": False}}]}
    )
    await hass.async_block_till_done()
    assert hass.states.get(light_id(hass)).state == STATE_OFF

    coordinator.handle_event("device", {"id": "dr154", "online": False})
    await hass.async_block_till_done()
    assert hass.states.get(light_id(hass)).state == STATE_UNAVAILABLE

    coordinator.handle_event("device", {"id": "dr154", "online": True})
    coordinator.handle_event(
        "state", {"channels": [{"channelId": 11, "state": {**EMPTY_STATE, "isOn": True}}]}
    )
    await hass.async_block_till_done()
    assert hass.states.get(light_id(hass)).state == STATE_ON


class FakeResponse:
    """Risposta SSE finta: righe come arrivano dall'hub."""

    def __init__(self, lines: list[str]) -> None:
        """Le righe del flusso."""
        self.content = self._iterate(lines)

    @staticmethod
    async def _iterate(lines: list[str]):
        for line in lines:
            yield (line + "\n").encode()


async def test_server_sent_events_are_parsed() -> None:
    """Eventi `data:` su una o più righe, separati da una riga vuota; il resto si ignora."""
    received: list[tuple[str, dict]] = []
    response = FakeResponse(
        [
            ": commento",
            "id: 1",
            'data: {"type": "state", "data": {"channels": []}}',
            "",
            "data: {",
            'data: "type": "device", "data": {"id": "dr154", "online": true}}',
            "",
            "data: non json",
            "",
        ]
    )
    await SheltrClient._read_events(
        MagicMock(content=response.content), lambda k, d: received.append((k, d))
    )
    assert received == [("state", {"channels": []}), ("device", {"id": "dr154", "online": True})]
