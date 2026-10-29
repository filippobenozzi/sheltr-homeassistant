"""Test delle entità: stato letto dal portale e comandi mandati."""

from __future__ import annotations

from typing import Any

from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.sheltr.const import DOMAIN
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACAction,
    HVACMode,
)
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN, CoverState
from homeassistant.components.light import ATTR_BRIGHTNESS, DOMAIN as LIGHT_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_OPEN_COVER,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import BASE_URL


def entity_id(hass: HomeAssistant, platform: str, unique_id: str) -> str:
    """Entity id dall'unique id (deviceId-collection-key)."""
    found = er.async_get(hass).async_get_entity_id(platform, DOMAIN, unique_id)
    assert found is not None, unique_id
    return found


def commands(mock: AiohttpClientMocker, path: str) -> list[Any]:
    """Corpi delle POST mandate a un percorso."""
    return [
        call[2] for call in mock.mock_calls if call[0] == "POST" and str(call[1]) == BASE_URL + path
    ]


async def call(hass: HomeAssistant, domain: str, service: str, target: str, **data: Any) -> None:
    """Chiama un servizio su un'entità e aspetta."""
    await hass.services.async_call(domain, service, {ATTR_ENTITY_ID: target, **data}, blocking=True)


async def test_entities_and_device(hass: HomeAssistant, setup_integration: MockConfigEntry) -> None:
    """Ogni canale diventa un'entità del dispositivo del suo gateway, nella stanza del portale."""
    light = entity_id(hass, LIGHT_DOMAIN, "dr154-channels-b1-c1")
    assert hass.states.get(light).state == STATE_ON
    assert hass.states.get(light).attributes["friendly_name"] == "Casa Demo · Quadro Lampadario"

    registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(registry, setup_integration.entry_id)
    device = next(d for d in devices if (DOMAIN, "dr154") in d.identifiers)
    assert (device.manufacturer, device.model, device.sw_version) == (
        "Sheltr",
        "USR DR154",
        "V1.3.04",
    )


async def test_light_and_dimmer(
    hass: HomeAssistant, setup_integration: MockConfigEntry, aioclient_mock: AiohttpClientMocker
) -> None:
    """Luce on/off; dimmer coi livelli 0-9 del bus su 0-255."""
    aioclient_mock.post(f"{BASE_URL}/api/channels/11/command", json={"id": "c1", "status": "sent"})
    aioclient_mock.post(f"{BASE_URL}/api/channels/12/command", json={"id": "c2", "status": "sent"})
    light = entity_id(hass, LIGHT_DOMAIN, "dr154-channels-b1-c1")
    dimmer = entity_id(hass, LIGHT_DOMAIN, "dr154-channels-b2-c1")

    await call(hass, LIGHT_DOMAIN, SERVICE_TURN_OFF, light)
    assert commands(aioclient_mock, "/api/channels/11/command") == [{"action": "off"}]

    assert hass.states.get(dimmer).attributes[ATTR_BRIGHTNESS] == round(5 * 255 / 9)
    await call(hass, LIGHT_DOMAIN, SERVICE_TURN_ON, dimmer, brightness=255)
    await call(hass, LIGHT_DOMAIN, SERVICE_TURN_ON, dimmer, brightness=1)
    assert commands(aioclient_mock, "/api/channels/12/command") == [
        {"action": "set", "level": 9},
        {"action": "set", "level": 1},
    ]


async def test_shutter(
    hass: HomeAssistant, setup_integration: MockConfigEntry, aioclient_mock: AiohttpClientMocker
) -> None:
    """Tapparella: chiusa se l'ultimo movimento è in giù; su, giù, stop."""
    aioclient_mock.post(f"{BASE_URL}/api/channels/13/command", json={"id": "c3", "status": "sent"})
    cover = entity_id(hass, COVER_DOMAIN, "dr154-channels-b3-c1")
    assert hass.states.get(cover).state == CoverState.CLOSED
    await call(hass, COVER_DOMAIN, SERVICE_OPEN_COVER, cover)
    assert commands(aioclient_mock, "/api/channels/13/command") == [{"action": "up"}]


async def test_thermostat(
    hass: HomeAssistant, setup_integration: MockConfigEntry, aioclient_mock: AiohttpClientMocker
) -> None:
    """Termostato: temperatura, setpoint, inverno = riscaldamento; setpoint e spegnimento."""
    aioclient_mock.post(f"{BASE_URL}/api/channels/14/command", json={"id": "c4", "status": "sent"})
    climate = entity_id(hass, CLIMATE_DOMAIN, "dr154-channels-b4-c1")
    state = hass.states.get(climate)
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 20.3
    assert state.attributes[ATTR_TEMPERATURE] == 21.5
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.HEATING

    await call(hass, CLIMATE_DOMAIN, SERVICE_SET_TEMPERATURE, climate, temperature=22)
    await call(
        hass, CLIMATE_DOMAIN, SERVICE_SET_HVAC_MODE, climate, **{ATTR_HVAC_MODE: HVACMode.OFF}
    )
    await call(
        hass, CLIMATE_DOMAIN, SERVICE_SET_HVAC_MODE, climate, **{ATTR_HVAC_MODE: HVACMode.COOL}
    )
    assert commands(aioclient_mock, "/api/channels/14/command") == [
        {"setpoint": 22.0},
        {"action": "off"},
        {"mode": "summer"},
    ]


async def test_sequence_input_and_connectivity(
    hass: HomeAssistant, setup_integration: MockConfigEntry, aioclient_mock: AiohttpClientMocker
) -> None:
    """Sequenza come pulsante, ingresso e collegamento del gateway come sensori."""
    aioclient_mock.post(f"{BASE_URL}/api/sequences/21/run", json={"ok": True})
    button = entity_id(hass, BUTTON_DOMAIN, "dr154-sequences-s1")
    await call(hass, BUTTON_DOMAIN, SERVICE_PRESS, button)
    assert commands(aioclient_mock, "/api/sequences/21/run") == [{}]

    assert (
        hass.states.get(entity_id(hass, BINARY_SENSOR_DOMAIN, "dr154-inputs-i1")).state == STATE_OFF
    )
    assert (
        hass.states.get(entity_id(hass, BINARY_SENSOR_DOMAIN, "dr154-connectivity")).state
        == STATE_ON
    )
