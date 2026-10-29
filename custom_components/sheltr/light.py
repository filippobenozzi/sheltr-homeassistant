"""Luci (on/off) e dimmer (livelli 0-9 del bus, 0-255 in Home Assistant)."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
import math
from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SheltrConfigEntry
from .entity import SheltrEntity, channels, track_entities

DIMMER_MAX = 9


async def async_setup_entry(
    hass: HomeAssistant, entry: SheltrConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Una luce per ogni canale luce o dimmer (anche quelli aggiunti dopo)."""
    coordinator = entry.runtime_data

    def build() -> dict[str, Callable[[], LightEntity]]:
        found: dict[str, Callable[[], LightEntity]] = {
            f"light-{c['id']}": partial(SheltrLight, coordinator, "channels", c)
            for c in channels(coordinator, "light")
        }
        found.update(
            {
                f"dimmer-{c['id']}": partial(SheltrDimmer, coordinator, "channels", c)
                for c in channels(coordinator, "dimmer")
            }
        )
        return found

    track_entities(coordinator, async_add_entities, build)


class SheltrLight(SheltrEntity, LightEntity):
    """Luce on/off."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    @property
    def is_on(self) -> bool | None:
        """Accesa, spenta o non ancora letta."""
        item = self.item
        return None if item is None else item["state"]["isOn"]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Accende."""
        await self.coordinator.client.command(self._item_id, {"action": "on"})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Spegne."""
        await self.coordinator.client.command(self._item_id, {"action": "off"})


class SheltrDimmer(SheltrEntity, LightEntity):
    """Dimmer: luminosità a 9 livelli."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    @property
    def is_on(self) -> bool | None:
        """Acceso se il livello è sopra zero."""
        item = self.item
        if item is None or item["state"]["level"] is None:
            return None
        return item["state"]["level"] > 0

    @property
    def brightness(self) -> int | None:
        """Livello 0-9 riportato su 0-255."""
        item = self.item
        level = None if item is None else item["state"]["level"]
        return None if level is None else round(level * 255 / DIMMER_MAX)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Accende, al livello chiesto o all'ultimo usato."""
        if ATTR_BRIGHTNESS in kwargs:
            level = max(1, min(DIMMER_MAX, math.ceil(kwargs[ATTR_BRIGHTNESS] * DIMMER_MAX / 255)))
            await self.coordinator.client.command(self._item_id, {"action": "set", "level": level})
        else:
            await self.coordinator.client.command(self._item_id, {"action": "on"})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Spegne."""
        await self.coordinator.client.command(self._item_id, {"action": "off"})
