"""Base delle entità: un dispositivo Home Assistant per ogni gateway Sheltr."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SheltrCoordinator

DEVICE_MODELS = {"esp": "Sheltr ESP", "usr": "USR DR154"}


def device_info(
    home: dict[str, Any], device: dict[str, Any], area: str | None = None
) -> DeviceInfo:
    """Dispositivo Home Assistant di un gateway, col nome dell'impianto."""
    return DeviceInfo(
        identifiers={(DOMAIN, device["id"])},
        name=f"{home['name']} · {device.get('name', device['id'])}",
        manufacturer="Sheltr",
        model=DEVICE_MODELS.get(device.get("type", ""), "Sheltr"),
        sw_version=device.get("firmware"),
        suggested_area=area,
    )


class SheltrEntity(CoordinatorEntity[SheltrCoordinator]):
    """Canale, sequenza o ingresso di un impianto."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: SheltrCoordinator, collection: str, item: dict[str, Any]
    ) -> None:
        """Entità di un elemento di `channels`, `sequences` o `inputs`."""
        super().__init__(coordinator)
        self._collection = collection
        self._item_id = item["id"]
        home = self._home_of(item)
        device = next(
            (d for d in home["devices"] if d["id"] == item["deviceId"]), {"id": item["deviceId"]}
        )
        room = next((r["name"] for r in home["rooms"] if r["id"] == item.get("roomId")), None)
        self._attr_unique_id = f"{item['deviceId']}-{collection}-{item.get('key', item['id'])}"
        self._attr_name = item["name"]
        self._attr_device_info = device_info(home, device, room)

    def _home_of(self, item: dict[str, Any]) -> dict[str, Any]:
        for home in self.coordinator.data.values():
            if any(entry["id"] == item["id"] for entry in home[self._collection]):
                return home
        return next(iter(self.coordinator.data.values()))

    @property
    def item(self) -> dict[str, Any] | None:
        """L'elemento com'è adesso nei dati del coordinatore."""
        return self.coordinator.find(self._collection, self._item_id)

    @property
    def available(self) -> bool:
        """Non disponibile se tolto dal portale o se il suo gateway è offline."""
        item = self.item
        return super().available and item is not None and item.get("online", True)


def channels(coordinator: SheltrCoordinator, kind: str) -> list[dict[str, Any]]:
    """Canali di un tipo (`light`, `dimmer`, `shutter`, `thermostat`) di tutti gli impianti."""
    return [c for home in coordinator.data.values() for c in home["channels"] if c["kind"] == kind]
