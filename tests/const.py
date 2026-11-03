"""Dati di prova: un portale con un impianto, come lo descrivono le API di Smart Domo Cerebro."""

from __future__ import annotations

import copy
from typing import Any

BASE_URL = "https://cloud.example.com"
TOKEN = "shltr_prova"
HOME_ID = "casa1"

ME_URL = f"{BASE_URL}/api/me"
HOMES_URL = f"{BASE_URL}/api/homes"
HOME_URL = f"{BASE_URL}/api/homes/{HOME_ID}"
REALTIME_URL = f"{BASE_URL}/api/me/realtime"

ME = {"id": "u-api", "name": "API · Casa Demo", "role": "user"}

EMPTY_STATE: dict[str, Any] = {
    "isOn": None,
    "level": None,
    "setpoint": None,
    "mode": None,
    "temperature": None,
    "active": None,
    "shutterAction": None,
    "updatedAt": None,
}


def channel(item_id: int, key: str, kind: str, name: str, **state: Any) -> dict[str, Any]:
    """Un canale del modulo `key` col suo stato."""
    return {
        "id": item_id,
        "key": key,
        "deviceId": "dr154",
        "boardId": int(key[1 : key.index("-")]),
        "boardName": f"Modulo {kind}",
        "kind": kind,
        "number": 1,
        "name": name,
        "roomId": 1,
        "online": True,
        "state": {**EMPTY_STATE, **state},
        "command": None,
    }


HOME: dict[str, Any] = {
    "id": HOME_ID,
    "name": "Casa Demo",
    "rooms": [{"id": 1, "name": "Sala"}],
    "devices": [
        {
            "id": "dr154",
            "name": "Quadro",
            "type": "usr",
            "claimed": True,
            "online": True,
            "firmware": "V1.3.04",
            "mode": "api",
        }
    ],
    "channels": [
        channel(11, "b1-c1", "light", "Lampadario", isOn=True),
        channel(12, "b2-c1", "dimmer", "Abat-jour", level=5),
        channel(13, "b3-c1", "shutter", "Tapparella", shutterAction="down"),
        channel(
            14,
            "b4-c1",
            "thermostat",
            "Termostato",
            isOn=True,
            setpoint=21.5,
            temperature=20.3,
            mode="winter",
            active=True,
        ),
    ],
    "sequences": [
        {"id": 21, "key": "s1", "deviceId": "dr154", "name": "Buonanotte", "roomId": None}
    ],
    "inputs": [
        {
            "id": 31,
            "key": "i1",
            "deviceId": "dr154",
            "name": "Porta",
            "roomId": None,
            "active": False,
        }
    ],
}


def home() -> dict[str, Any]:
    """Una copia fresca dell'impianto (i test la modificano)."""
    return copy.deepcopy(HOME)
