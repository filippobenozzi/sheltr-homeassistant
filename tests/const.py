"""Payload di esempio del portale Sheltr Cloud usati nei test."""

from __future__ import annotations

from typing import Any

BASE_URL = "http://sheltr.local:8080"
INSTANCE_ID = "casa-demo"
TOKEN = "token-di-prova"

CONFIG_DATA = {
    "url": BASE_URL,
    "instance_id": INSTANCE_ID,
    "username": "filippo",
    "password": "segreta",
    "verify_ssl": True,
}

LOGIN_URL = f"{BASE_URL}/api/instances/{INSTANCE_ID}/auth/login"
INSTANCE_URL = f"{BASE_URL}/api/instances/{INSTANCE_ID}"
STATUS_URL = f"{INSTANCE_URL}/status"
POLL_URL = f"{INSTANCE_URL}/poll"
LIGHTS_URL = f"{INSTANCE_URL}/lights/command"
DIMMERS_URL = f"{INSTANCE_URL}/dimmers/command"
SHUTTERS_URL = f"{INSTANCE_URL}/shutters/command"
THERMOSTATS_URL = f"{INSTANCE_URL}/thermostats/command"

INSTANCE: dict[str, Any] = {
    "id": INSTANCE_ID,
    "name": "Casa Demo",
    "deviceType": "sheltr_4g",
    "device": {"type": "sheltr_4g", "label": "Sheltr 4G / DR154"},
    "protocolVersion": "1.6",
    "dataSaver": False,
    "heartbeatMinutes": 30,
    "boards": [
        {"id": "board-1", "name": "Scheda Luci", "address": 1, "kind": "light"},
        {"id": "board-2", "name": "Scheda Tapparelle", "address": 2, "kind": "shutter"},
        {"id": "board-3", "name": "Scheda Dimmer", "address": 3, "kind": "dimmer"},
        {"id": "board-4", "name": "Scheda Termostato", "address": 4, "kind": "thermostat"},
    ],
    "mqtt": {"configTopic": f"/{INSTANCE_ID}/config"},
    "auth": {"username": "", "passwordConfigured": True},
    "updatedAt": "2026-07-25T09:00:00+00:00",
    "controlUrl": f"/control/{INSTANCE_ID}",
}


def _channel(
    board_id: str, board_name: str, address: int, kind: str, channel: int, name: str, room: str
) -> dict[str, Any]:
    return {
        "id": f"{board_id}-c{channel}",
        "boardId": board_id,
        "boardName": board_name,
        "address": address,
        "channel": channel,
        "kind": kind,
        "name": name,
        "room": room,
        "notifyOnChange": False,
    }


def build_status(**overrides: Any) -> dict[str, Any]:
    """Costruisce una risposta `/status` con una scheda per tipo."""
    light = _channel("board-1", "Scheda Luci", 1, "light", 1, "Luce cucina", "Cucina")
    light["isOn"] = False

    shutter = _channel(
        "board-2", "Scheda Tapparelle", 2, "shutter", 1, "Tapparella cucina", "Cucina"
    )
    shutter["action"] = "up"

    dimmer = _channel("board-3", "Scheda Dimmer", 3, "dimmer", 1, "Dimmer salotto", "Salotto")
    dimmer["level"] = 0
    dimmer["isOn"] = False

    thermostat = _channel(
        "board-4", "Scheda Termostato", 4, "thermostat", 1, "Termostato salotto", "Salotto"
    )
    thermostat.update(
        {"temperature": 21.5, "setpoint": 20.0, "mode": "winter", "isOn": True, "isActive": False}
    )

    status: dict[str, Any] = {
        "instanceId": INSTANCE_ID,
        "updatedAt": "2026-07-25T10:00:00+00:00",
        "refreshErrors": [],
        "commandTopic": f"/{INSTANCE_ID}/cmd",
        "responseTopic": f"/{INSTANCE_ID}/status",
        "payloadFormat": "frame_bytes",
        "dataSaver": False,
        "device": {
            "online": True,
            "lastSeenAt": "2026-07-25T09:59:00+00:00",
            "heartbeatMinutes": 30,
        },
        "rooms": [
            {
                "name": "Cucina",
                "color": "#f9d5d3",
                "lights": [light],
                "dimmers": [],
                "shutters": [shutter],
                "thermostats": [],
            },
            {
                "name": "Salotto",
                "color": "#d4e5f7",
                "lights": [],
                "dimmers": [dimmer],
                "shutters": [],
                "thermostats": [thermostat],
            },
        ],
        "roomColors": {},
        "roomPalette": [],
        "boards": INSTANCE["boards"],
    }
    status.update(overrides)
    return status


STATUS = build_status()
