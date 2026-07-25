"""Sensori derivati dallo stato dell'impianto Sheltr."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import KIND_THERMOSTAT
from .coordinator import SheltrConfigEntry
from .entity import SheltrEntity, SheltrInstanceEntity, async_setup_channel_entities

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SheltrConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Crea le temperature dei termostati e l'ultimo contatto dell'impianto."""
    coordinator = entry.runtime_data
    async_add_entities([SheltrLastSeenSensor(coordinator)])
    async_setup_channel_entities(
        coordinator,
        entry,
        async_add_entities,
        (KIND_THERMOSTAT,),
        SheltrTemperatureSensor,
    )


class SheltrTemperatureSensor(SheltrEntity, SensorEntity):
    """Temperatura misurata dalla sonda di un termostato."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator, channel_id: str) -> None:
        """Aggiunge il suffisso `_temperature` all'identificativo del canale."""
        super().__init__(coordinator, channel_id)
        self._attr_unique_id = f"{coordinator.instance_id}_{channel_id}_temperature"

    @property
    def name(self) -> str:
        """Nome del canale seguito da «temperatura»."""
        return f"{self.channel.get('name') or self._channel_id} temperatura"

    @property
    def native_value(self) -> float | None:
        """Ultima temperatura riportata dal modulo."""
        value = self.channel.get("temperature")
        return float(value) if isinstance(value, (int, float)) else None


class SheltrLastSeenSensor(SheltrInstanceEntity, SensorEntity):
    """Ultimo messaggio ricevuto dal dispositivo (heartbeat)."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "last_seen"

    def __init__(self, coordinator) -> None:
        """Registra l'entità sul dispositivo impianto."""
        super().__init__(coordinator, "last_seen")

    @property
    def native_value(self) -> datetime | None:
        """Timestamp dell'ultimo heartbeat ricevuto dal portale."""
        last_seen = self.coordinator.data.last_seen
        if not last_seen:
            return None
        value = dt_util.parse_datetime(last_seen)
        if value is None:
            return None
        return value if value.tzinfo else value.replace(tzinfo=dt_util.UTC)
