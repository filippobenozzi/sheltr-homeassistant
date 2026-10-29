"""Tapparelle: su, giù, stop. Il bus non riporta la posizione."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Any

from homeassistant.components.cover import CoverDeviceClass, CoverEntity, CoverEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SheltrConfigEntry
from .entity import SheltrEntity, channels, track_entities


async def async_setup_entry(
    hass: HomeAssistant, entry: SheltrConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Una tapparella per ogni canale tapparella (anche quelli aggiunti dopo)."""
    coordinator = entry.runtime_data

    def build() -> dict[str, Callable[[], CoverEntity]]:
        return {
            f"shutter-{c['id']}": partial(SheltrShutter, coordinator, "channels", c)
            for c in channels(coordinator, "shutter")
        }

    track_entities(coordinator, async_add_entities, build)


class SheltrShutter(SheltrEntity, CoverEntity):
    """Tapparella in stato presunto: si conosce solo l'ultimo movimento."""

    _attr_device_class = CoverDeviceClass.SHUTTER
    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )
    _attr_assumed_state = True

    @property
    def is_closed(self) -> bool | None:
        """Chiusa se l'ultimo movimento è stato in giù."""
        item = self.item
        action = None if item is None else item["state"].get("shutterAction")
        if action == "down":
            return True
        if action == "up":
            return False
        return None

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Su."""
        await self.coordinator.client.command(self._item_id, {"action": "up"})

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Giù."""
        await self.coordinator.client.command(self._item_id, {"action": "down"})

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop."""
        await self.coordinator.client.command(self._item_id, {"action": "stop"})
