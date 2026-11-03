"""Dispositivi Home Assistant: un gateway per Cerebro Remote o Cerebro Lite, un modulo per scheda sul bus."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN

DEVICE_MODELS = {"esp": "Cerebro Lite", "usr": "Cerebro Remote"}
BOARD_MODELS = {
    "light": "Modulo luci",
    "dimmer": "Modulo dimmer",
    "shutter": "Modulo tapparelle",
    "thermostat": "Modulo termostato",
}
# Dalle versioni recenti di Home Assistant il modulo si collega al gateway col suo id nel
# registro (via_device_id); prima con gli identificativi (via_device).
VIA_DEVICE_ID = "via_device_id" in DeviceInfo.__annotations__


def device_info(home: dict[str, Any], device: dict[str, Any]) -> DeviceInfo:
    """Gateway (per un DR154 in modalità API, che non sta in un impianto, solo il suo nome)."""
    name = device.get("name", device["id"])
    return DeviceInfo(
        identifiers={(DOMAIN, device["id"])},
        name=name if home.get("internal") else f"{home['name']} · {name}",
        manufacturer="Smart Domo Cerebro",
        model=DEVICE_MODELS.get(device.get("type", ""), "Smart Domo Cerebro"),
        sw_version=device.get("firmware"),
    )


def board_key(channel: dict[str, Any]) -> str:
    """Modulo di un canale dalla sua chiave ("b12-c1" → "b12")."""
    return channel.get("key", "").split("-", 1)[0] or f"board{channel.get('boardId')}"


def board_info(home: dict[str, Any], channel: dict[str, Any], gateway_id: str | None) -> DeviceInfo:
    """Modulo di un canale, collegato al gateway, nella stanza dei suoi canali (se è una sola)."""
    key = board_key(channel)
    siblings = [
        c for c in home["channels"] if c["deviceId"] == channel["deviceId"] and board_key(c) == key
    ]
    rooms = {c.get("roomId") for c in siblings}
    room_id = rooms.pop() if len(rooms) == 1 else None
    address = key[1:] if key.startswith("b") else "?"
    info = DeviceInfo(
        identifiers={(DOMAIN, f"{channel['deviceId']}-{key}")},
        name=channel.get("boardName") or f"Modulo {address}",
        manufacturer="Smart Domo Cerebro",
        model=f"{BOARD_MODELS.get(channel['kind'], 'Modulo')} · indirizzo {address}",
        suggested_area=next((r["name"] for r in home["rooms"] if r["id"] == room_id), None),
    )
    if VIA_DEVICE_ID and gateway_id is not None:
        info["via_device_id"] = gateway_id
    else:
        info["via_device"] = (DOMAIN, channel["deviceId"])  # type: ignore[typeddict-unknown-key]
    return info
