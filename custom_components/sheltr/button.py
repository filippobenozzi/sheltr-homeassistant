"""Pulsante per forzare il polling dei moduli Sheltr."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
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
    """Crea il pulsante «Aggiorna stato»."""
    async_add_entities([SheltrRefreshButton(entry.runtime_data)])


class SheltrRefreshButton(SheltrInstanceEntity, ButtonEntity):
    """Esegue il polling attivo di tutti i moduli, come il tasto «Aggiorna» del portale."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "refresh"

    def __init__(self, coordinator) -> None:
        """Registra l'entità sul dispositivo impianto."""
        super().__init__(coordinator, "refresh")

    async def async_press(self) -> None:
        """Interroga i moduli e aggiorna tutte le entità."""
        await self.coordinator.async_force_active_poll()
