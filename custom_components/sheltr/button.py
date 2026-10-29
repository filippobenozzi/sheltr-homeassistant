"""Sequenze dei gateway ESP: un pulsante per avviarle."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SheltrConfigEntry
from .entity import SheltrEntity, track_entities


async def async_setup_entry(
    hass: HomeAssistant, entry: SheltrConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Un pulsante per ogni sequenza (anche quelle aggiunte dopo)."""
    coordinator = entry.runtime_data

    def build() -> dict[str, Callable[[], ButtonEntity]]:
        return {
            f"sequence-{s['id']}": partial(SheltrSequence, coordinator, "sequences", s)
            for home in coordinator.data.values()
            for s in home["sequences"]
        }

    track_entities(coordinator, async_add_entities, build)


class SheltrSequence(SheltrEntity, ButtonEntity):
    """Avvia una sequenza."""

    _attr_icon = "mdi:play-box-multiple"

    async def async_press(self) -> None:
        """Avvia."""
        await self.coordinator.client.run_sequence(self._item_id)
