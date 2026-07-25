"""Test di importazione delle schede e dei comandi."""

from __future__ import annotations

from typing import Any

from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.sheltr.const import DOMAIN
from homeassistant.components.button import SERVICE_PRESS
from homeassistant.components.climate import (
    ATTR_HVAC_ACTION,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.components.light import ATTR_BRIGHTNESS, DOMAIN as LIGHT_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import (
    DIMMERS_URL,
    INSTANCE_ID,
    LIGHTS_URL,
    SHUTTERS_URL,
    STATUS_URL,
    THERMOSTATS_URL,
    build_status,
)


def _entity_id(hass: HomeAssistant, platform: str, channel_id: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(
        platform, DOMAIN, f"{INSTANCE_ID}_{channel_id}"
    )
    assert entity_id is not None, f"entità mancante per {channel_id}"
    return entity_id


def _last_call(mock: AiohttpClientMocker, url: str) -> dict[str, Any]:
    calls = [call for call in mock.mock_calls if str(call[1]) == url]
    assert calls, f"nessuna chiamata a {url}"
    return calls[-1][2]


def _arm(mock: AiohttpClientMocker, url: str, payload: dict[str, Any]) -> None:
    """Registra la risposta a un comando.

    Il mocker usa sempre la prima risposta registrata per una URL, quindi va
    azzerato prima di riarmarlo con un payload diverso.
    """
    mock.clear_requests()
    mock.get(STATUS_URL, json=build_status())
    mock.post(url, json=payload)


async def test_boards_are_imported(hass: HomeAssistant, setup_integration: MockConfigEntry) -> None:
    """Ogni canale delle schede diventa un'entità del tipo corretto."""
    light = hass.states.get(_entity_id(hass, LIGHT_DOMAIN, "board-1-c1"))
    assert light is not None
    assert light.state == STATE_OFF
    assert light.attributes["friendly_name"] == "Scheda Luci Luce cucina"
    assert light.attributes["address"] == 1
    assert light.attributes["room"] == "Cucina"

    cover = hass.states.get(_entity_id(hass, COVER_DOMAIN, "board-2-c1"))
    assert cover is not None
    assert cover.state == "open"
    assert cover.attributes["assumed_state"] is True

    dimmer = hass.states.get(_entity_id(hass, LIGHT_DOMAIN, "board-3-c1"))
    assert dimmer is not None
    assert dimmer.state == STATE_OFF
    assert dimmer.attributes["supported_color_modes"] == ["brightness"]

    climate = hass.states.get(_entity_id(hass, CLIMATE_DOMAIN, "board-4-c1"))
    assert climate is not None
    assert climate.state == HVACMode.HEAT
    assert climate.attributes["current_temperature"] == 21.5
    assert climate.attributes["temperature"] == 20.0
    assert climate.attributes[ATTR_HVAC_ACTION] == "idle"

    temperature = hass.states.get(_entity_id(hass, "sensor", "board-4-c1_temperature"))
    assert temperature is not None
    assert temperature.state == "21.5"


async def test_devices_are_created_per_board(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Ogni scheda è un dispositivo collegato all'impianto."""
    registry = dr.async_get(hass)
    hub = registry.async_get_device(identifiers={(DOMAIN, INSTANCE_ID)})
    assert hub is not None
    assert hub.name == "Casa Demo"
    assert hub.model == "Sheltr 4G / DR154"

    board = registry.async_get_device(identifiers={(DOMAIN, f"{INSTANCE_ID}::board-1")})
    assert board is not None
    assert board.name == "Scheda Luci"
    assert board.via_device_id == hub.id
    assert board.model == "Scheda luci · indirizzo 1"


async def test_instance_entities(hass: HomeAssistant, setup_integration: MockConfigEntry) -> None:
    """L'impianto espone connettività, ultimo contatto e pulsante di refresh."""
    assert hass.states.get(_entity_id(hass, "binary_sensor", "online")).state == STATE_ON
    assert hass.states.get(_entity_id(hass, "sensor", "last_seen")) is not None
    assert hass.states.get(_entity_id(hass, "button", "refresh")) is not None


async def test_light_turn_on(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_portal: AiohttpClientMocker,
) -> None:
    """L'accensione invia il comando e aggiorna subito lo stato."""
    _arm(
        mock_portal,
        LIGHTS_URL,
        {"ok": True, "sent": [{"id": "board-1-c1", "action": "on", "isOn": True}]},
    )
    entity_id = _entity_id(hass, LIGHT_DOMAIN, "board-1-c1")

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    await hass.async_block_till_done()

    assert _last_call(mock_portal, LIGHTS_URL) == {
        "lightId": "board-1-c1",
        "action": "on",
    }
    assert hass.states.get(entity_id).state == STATE_ON


async def test_dimmer_brightness(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_portal: AiohttpClientMocker,
) -> None:
    """La luminosità 0..255 viene convertita nel livello 0..9 del protocollo."""
    _arm(
        mock_portal,
        DIMMERS_URL,
        {
            "ok": True,
            "sent": [{"id": "board-3-c1", "action": "set", "level": 5, "isOn": True}],
        },
    )
    entity_id = _entity_id(hass, LIGHT_DOMAIN, "board-3-c1")

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 142},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert _last_call(mock_portal, DIMMERS_URL) == {
        "dimmerId": "board-3-c1",
        "action": "set",
        "level": 5,
    }
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 142


async def test_cover_close(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_portal: AiohttpClientMocker,
) -> None:
    """La chiusura invia l'azione `down`."""
    _arm(
        mock_portal,
        SHUTTERS_URL,
        {"ok": True, "sent": [{"id": "board-2-c1", "action": "down"}]},
    )
    entity_id = _entity_id(hass, COVER_DOMAIN, "board-2-c1")

    await hass.services.async_call(
        COVER_DOMAIN, SERVICE_CLOSE_COVER, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    await hass.async_block_till_done()

    assert _last_call(mock_portal, SHUTTERS_URL) == {
        "shutterId": "board-2-c1",
        "action": "down",
    }
    assert hass.states.get(entity_id).state == "closed"


async def test_climate_commands(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_portal: AiohttpClientMocker,
) -> None:
    """Setpoint, stagione e spegnimento del termostato."""
    entity_id = _entity_id(hass, CLIMATE_DOMAIN, "board-4-c1")

    _arm(
        mock_portal,
        THERMOSTATS_URL,
        {
            "ok": True,
            "sent": [
                {
                    "id": "board-4-c1",
                    "setpoint": 22.5,
                    "mode": "winter",
                    "isOn": True,
                    "isActive": True,
                }
            ],
        },
    )
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 22.5},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert _last_call(mock_portal, THERMOSTATS_URL) == {
        "thermostatId": "board-4-c1",
        "setpoint": 22.5,
    }
    state = hass.states.get(entity_id)
    assert state.attributes["temperature"] == 22.5
    assert state.attributes[ATTR_HVAC_ACTION] == "heating"

    _arm(
        mock_portal,
        THERMOSTATS_URL,
        {
            "ok": True,
            "sent": [
                {
                    "id": "board-4-c1",
                    "setpoint": 22.5,
                    "mode": "summer",
                    "isOn": True,
                    "isActive": False,
                }
            ],
        },
    )
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, "hvac_mode": HVACMode.COOL},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert _last_call(mock_portal, THERMOSTATS_URL) == {
        "thermostatId": "board-4-c1",
        "mode": "summer",
        "power": True,
    }
    assert hass.states.get(entity_id).state == HVACMode.COOL

    _arm(
        mock_portal,
        THERMOSTATS_URL,
        {"ok": True, "sent": [{"id": "board-4-c1", "isOn": False}]},
    )
    await hass.services.async_call(
        CLIMATE_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    await hass.async_block_till_done()

    assert _last_call(mock_portal, THERMOSTATS_URL) == {
        "thermostatId": "board-4-c1",
        "power": False,
    }
    assert hass.states.get(entity_id).state == HVACMode.OFF


async def test_refresh_button_polls_modules(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_portal: AiohttpClientMocker,
) -> None:
    """Il pulsante forza il polling attivo (`refresh=1`)."""
    mock_portal.clear_requests()
    status = build_status()
    status["rooms"][0]["lights"][0]["isOn"] = True
    mock_portal.get(STATUS_URL, json=status)

    await hass.services.async_call(
        "button",
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: _entity_id(hass, "button", "refresh")},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert any(
        str(call[1]).startswith(STATUS_URL) and call[1].query.get("refresh") == "1"
        for call in mock_portal.mock_calls
    )
    assert hass.states.get(_entity_id(hass, LIGHT_DOMAIN, "board-1-c1")).state == STATE_ON


async def test_new_board_is_added_later(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_portal: AiohttpClientMocker,
) -> None:
    """Una scheda aggiunta nel portale compare al successivo aggiornamento."""
    status = build_status()
    status["rooms"][0]["lights"].append(
        {
            "id": "board-5-c1",
            "boardId": "board-5",
            "boardName": "Scheda Luci Piano 1",
            "address": 5,
            "channel": 1,
            "kind": "light",
            "name": "Luce studio",
            "room": "Cucina",
            "isOn": None,
        }
    )
    mock_portal.clear_requests()
    mock_portal.get(STATUS_URL, json=status)

    coordinator = setup_integration.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(_entity_id(hass, LIGHT_DOMAIN, "board-5-c1")).state == STATE_UNKNOWN


async def test_entities_unavailable_when_device_offline(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_portal: AiohttpClientMocker,
) -> None:
    """Dispositivo offline: i canali diventano non disponibili."""
    status = build_status()
    status["device"]["online"] = False
    mock_portal.clear_requests()
    mock_portal.get(STATUS_URL, json=status)

    await setup_integration.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(_entity_id(hass, LIGHT_DOMAIN, "board-1-c1")).state == "unavailable"
    assert hass.states.get(_entity_id(hass, "binary_sensor", "online")).state == STATE_OFF
