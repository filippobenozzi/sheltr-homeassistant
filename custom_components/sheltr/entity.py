"""Base delle entità: i canali nel loro modulo, sequenze e ingressi nel gateway."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import SheltrCoordinator
from .devices import board_info, device_info


class SheltrEntity(CoordinatorEntity[SheltrCoordinator]):
    """Canale (nel suo modulo), sequenza o ingresso (nel gateway) di un impianto."""

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
        self._attr_unique_id = f"{item['deviceId']}-{collection}-{item.get('key', item['id'])}"
        self._attr_name = item["name"]
        if collection == "channels":
            self._attr_device_info = board_info(home, item, coordinator.gateway(home, device))
        else:
            self._attr_device_info = device_info(home, device)

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


def track_entities(
    coordinator: SheltrCoordinator,
    async_add_entities: AddEntitiesCallback,
    build: Callable[[], dict[str, Callable[[], Entity]]],
) -> None:
    """Aggiunge le entità che ci sono e quelle dei moduli aggiunti dopo nel portale."""
    known: set[str] = set()

    @callback
    def add_new() -> None:
        new = {key: make for key, make in build().items() if key not in known}
        if new:
            known.update(new)
            async_add_entities([make() for make in new.values()])

    add_new()
    if coordinator.config_entry is not None:
        coordinator.config_entry.async_on_unload(coordinator.async_add_listener(add_new))
