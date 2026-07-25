"""Stato di connessione del dispositivo Sheltr."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SheltrConfigEntry
from .entity import SheltrInstanceEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SheltrConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Crea il sensore di connettività dell'impianto."""
    async_add_entities([SheltrOnlineBinarySensor(entry.runtime_data)])


class SheltrOnlineBinarySensor(SheltrInstanceEntity, BinarySensorEntity):
    """Dispositivo raggiungibile secondo l'heartbeat configurato sul portale."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "device_online"

    def __init__(self, coordinator) -> None:
        """Registra l'entità sul dispositivo impianto."""
        super().__init__(coordinator, "online")

    @property
    def is_on(self) -> bool | None:
        """`None` quando l'heartbeat non è configurato sull'istanza."""
        return self.coordinator.data.online

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Dettagli dell'heartbeat riportati dal portale."""
        data = self.coordinator.data
        return {
            "last_seen": data.last_seen,
            "heartbeat_minutes": data.heartbeat_minutes,
            "data_saver": data.data_saver,
        }
