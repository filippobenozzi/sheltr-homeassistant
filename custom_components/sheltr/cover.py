"""Tapparelle delle schede Sheltr."""

from __future__ import annotations

from typing import Any

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import KIND_SHUTTER
from .coordinator import SheltrConfigEntry
from .entity import SheltrEntity, async_setup_channel_entities

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SheltrConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Crea una tapparella per ogni canale di tipo `shutter`."""
    async_setup_channel_entities(
        entry.runtime_data,
        entry,
        async_add_entities,
        (KIND_SHUTTER,),
        SheltrCover,
    )


class SheltrCover(SheltrEntity, CoverEntity):
    """Canale tapparella: il protocollo espone solo su/giù/stop, senza posizione."""

    _attr_device_class = CoverDeviceClass.SHUTTER
    _attr_assumed_state = True
    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )

    @property
    def is_closed(self) -> bool | None:
        """Stato dedotto dall'ultimo comando inviato: il modulo non riporta la posizione."""
        action = self.channel.get("action")
        if action == "down":
            return True
        if action == "up":
            return False
        return None

    @property
    def is_opening(self) -> bool:
        """La tapparella sta salendo (movimento confermato dal modulo)."""
        return self.channel.get("action") == "up" and self.channel.get("isActive") is True

    @property
    def is_closing(self) -> bool:
        """La tapparella sta scendendo (movimento confermato dal modulo)."""
        return self.channel.get("action") == "down" and self.channel.get("isActive") is True

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Alza la tapparella."""
        await self.coordinator.async_shutter_command(self._channel_id, "up")

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Abbassa la tapparella."""
        await self.coordinator.async_shutter_command(self._channel_id, "down")

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Ferma la tapparella."""
        await self.coordinator.async_shutter_command(self._channel_id, "stop")
