"""Luci e dimmer delle schede Sheltr."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DIMMER_MAX_LEVEL, KIND_DIMMER, KIND_LIGHT
from .coordinator import SheltrConfigEntry, SheltrCoordinator
from .entity import SheltrEntity, async_setup_channel_entities

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SheltrConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Crea un'entità luce per ogni canale di tipo `light` o `dimmer`."""

    def _factory(coordinator: SheltrCoordinator, channel_id: str) -> Entity:
        if coordinator.data.channels[channel_id].get("kind") == KIND_DIMMER:
            return SheltrDimmer(coordinator, channel_id)
        return SheltrLight(coordinator, channel_id)

    async_setup_channel_entities(
        entry.runtime_data, entry, async_add_entities, (KIND_LIGHT, KIND_DIMMER), _factory
    )


class SheltrLight(SheltrEntity, LightEntity):
    """Canale relè di una scheda luci."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    @property
    def is_on(self) -> bool | None:
        """Stato del relè; `None` finché il modulo non risponde."""
        value = self.channel.get("isOn")
        return value if isinstance(value, bool) else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Accende la luce."""
        await self.coordinator.async_light_command(self._channel_id, "on")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Spegne la luce."""
        await self.coordinator.async_light_command(self._channel_id, "off")


class SheltrDimmer(SheltrEntity, LightEntity):
    """Canale dimmer (livello 0..9 sul protocollo, 0..255 in Home Assistant)."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    @property
    def is_on(self) -> bool | None:
        """Acceso quando il livello è maggiore di zero."""
        value = self.channel.get("isOn")
        if isinstance(value, bool):
            return value
        level = self.channel.get("level")
        return level > 0 if isinstance(level, int) else None

    @property
    def brightness(self) -> int | None:
        """Livello del dimmer riportato sulla scala 0..255."""
        level = self.channel.get("level")
        if not isinstance(level, (int, float)):
            return None
        return round(max(0, min(DIMMER_MAX_LEVEL, int(level))) * 255 / DIMMER_MAX_LEVEL)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Accende il dimmer, impostando il livello se richiesto."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if brightness is None:
            await self.coordinator.async_dimmer_command(self._channel_id, "on")
            return
        level = round(int(brightness) * DIMMER_MAX_LEVEL / 255)
        level = max(1, min(DIMMER_MAX_LEVEL, level))
        await self.coordinator.async_dimmer_command(self._channel_id, "set", level)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Spegne il dimmer."""
        await self.coordinator.async_dimmer_command(self._channel_id, "off")
