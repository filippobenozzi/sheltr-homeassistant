"""Classi base e helper condivisi dalle entità Sheltr."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, KIND_LABELS, MANUFACTURER
from .coordinator import SheltrConfigEntry, SheltrCoordinator


def instance_device_info(coordinator: SheltrCoordinator) -> DeviceInfo:
    """Dispositivo «hub» che rappresenta l'impianto sul portale."""
    device = coordinator.instance.get("device")
    model = device.get("label") if isinstance(device, dict) else None
    protocol = coordinator.instance.get("protocolVersion")
    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.instance_id)},
        manufacturer=MANUFACTURER,
        name=coordinator.instance_name,
        model=model or coordinator.instance.get("deviceType") or "Sheltr Cloud",
        sw_version=f"protocollo {protocol}" if protocol else None,
        configuration_url=coordinator.client.control_url,
    )


def board_device_info(coordinator: SheltrCoordinator, channel: dict[str, Any]) -> DeviceInfo:
    """Dispositivo per la singola scheda, agganciato all'impianto."""
    board_id = channel.get("boardId") or coordinator.instance_id
    board_name = channel.get("boardName") or board_id
    model = KIND_LABELS.get(channel.get("kind", ""), "Scheda Sheltr")
    address = channel.get("address")
    if address is not None:
        model = f"{model} · indirizzo {address}"

    return DeviceInfo(
        identifiers={(DOMAIN, f"{coordinator.instance_id}::{board_id}")},
        via_device=(DOMAIN, coordinator.instance_id),
        manufacturer=MANUFACTURER,
        name=str(board_name),
        model=model,
    )


class SheltrEntity(CoordinatorEntity[SheltrCoordinator]):
    """Entità collegata a un canale di una scheda Sheltr."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SheltrCoordinator, channel_id: str) -> None:
        """Memorizza il canale e costruisce identificativi e dispositivo."""
        super().__init__(coordinator)
        self._channel_id = channel_id
        self._snapshot: dict[str, Any] = dict(coordinator.data.channels.get(channel_id, {}))
        self._attr_unique_id = f"{coordinator.instance_id}_{channel_id}"
        self._attr_device_info = board_device_info(coordinator, self._snapshot)

    @property
    def channel(self) -> dict[str, Any]:
        """Ultimo stato noto del canale."""
        current = self.coordinator.data.channels.get(self._channel_id)
        if current is not None:
            self._snapshot = current
        return self._snapshot

    @property
    def name(self) -> str | None:
        """Nome del canale così come configurato sul portale."""
        name = self.channel.get("name")
        return str(name) if name else None

    @property
    def available(self) -> bool:
        """Non disponibile se il canale sparisce o se il modulo risulta offline."""
        if not super().available:
            return False
        if self._channel_id not in self.coordinator.data.channels:
            return False
        return self.coordinator.data.online is not False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Dettagli utili del protocollo (scheda, indirizzo, canale, stanza)."""
        channel = self.channel
        return {
            "instance_id": self.coordinator.instance_id,
            "channel_id": self._channel_id,
            "board_id": channel.get("boardId"),
            "address": channel.get("address"),
            "channel": channel.get("channel"),
            "room": channel.get("room"),
        }


class SheltrInstanceEntity(CoordinatorEntity[SheltrCoordinator]):
    """Entità legata all'impianto nel suo complesso."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SheltrCoordinator, key: str) -> None:
        """Aggancia l'entità al dispositivo hub dell'impianto."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.instance_id}_{key}"
        self._attr_device_info = instance_device_info(coordinator)


@callback
def async_setup_channel_entities(
    coordinator: SheltrCoordinator,
    entry: SheltrConfigEntry,
    async_add_entities: AddEntitiesCallback,
    kinds: Iterable[str],
    factory: Callable[[SheltrCoordinator, str], Entity],
) -> None:
    """Aggiunge le entità dei canali richiesti, anche per le schede create dopo."""
    wanted = set(kinds)
    known: set[str] = set()

    @callback
    def _async_add_new() -> None:
        if coordinator.data is None:
            return
        new_entities: list[Entity] = []
        for channel_id, channel in coordinator.data.channels.items():
            if channel_id in known or channel.get("kind") not in wanted:
                continue
            known.add(channel_id)
            new_entities.append(factory(coordinator, channel_id))
        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new))
    _async_add_new()
