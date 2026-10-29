"""Sequenze dei gateway ESP: un pulsante per avviarle."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SheltrConfigEntry
from .entity import SheltrEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: SheltrConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Un pulsante per ogni sequenza."""
    coordinator = entry.runtime_data
    async_add_entities(
        SheltrSequence(coordinator, "sequences", s)
        for home in coordinator.data.values()
        for s in home["sequences"]
    )


class SheltrSequence(SheltrEntity, ButtonEntity):
    """Avvia una sequenza."""

    _attr_icon = "mdi:play-box-multiple"

    async def async_press(self) -> None:
        """Avvia."""
        await self.coordinator.client.run_sequence(self._item_id)
