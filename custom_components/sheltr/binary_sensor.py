"""Ingressi dei gateway ESP (contatti, pulsanti) e collegamento dei gateway."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SheltrConfigEntry
from .coordinator import SheltrCoordinator
from .entity import SheltrEntity, device_info


async def async_setup_entry(
    hass: HomeAssistant, entry: SheltrConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Un sensore per ogni ingresso e uno di collegamento per ogni gateway."""
    coordinator = entry.runtime_data
    entities: list[BinarySensorEntity] = [
        SheltrInput(coordinator, "inputs", i)
        for home in coordinator.data.values()
        for i in home["inputs"]
    ]
    entities += [
        SheltrConnectivity(coordinator, home, d)
        for home in coordinator.data.values()
        for d in home["devices"]
        if d["claimed"]
    ]
    async_add_entities(entities)


class SheltrInput(SheltrEntity, BinarySensorEntity):
    """Ingresso: attivo o no."""

    @property
    def is_on(self) -> bool | None:
        """Attivo."""
        item = self.item
        return None if item is None else bool(item["active"])

    @property
    def available(self) -> bool:
        """Disponibile finché il portale lo riporta."""
        return self.coordinator.last_update_success and self.item is not None


class SheltrConnectivity(CoordinatorEntity[SheltrCoordinator], BinarySensorEntity):
    """Il gateway è collegato al portale."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_name = "Collegamento"

    def __init__(
        self, coordinator: SheltrCoordinator, home: dict[str, Any], device: dict[str, Any]
    ) -> None:
        """Sensore di collegamento di un gateway."""
        super().__init__(coordinator)
        self._device_id = device["id"]
        self._attr_unique_id = f"{device['id']}-connectivity"
        self._attr_device_info = device_info(home, device)

    @property
    def is_on(self) -> bool | None:
        """Online."""
        for home in self.coordinator.data.values():
            for device in home["devices"]:
                if device["id"] == self._device_id:
                    return bool(device["online"])
        return None
