"""Termostati delle schede Sheltr."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    KIND_THERMOSTAT,
    MODE_SUMMER,
    MODE_WINTER,
    THERMOSTAT_MAX_TEMP,
    THERMOSTAT_MIN_TEMP,
    THERMOSTAT_TEMP_STEP,
)
from .coordinator import SheltrConfigEntry
from .entity import SheltrEntity, async_setup_channel_entities

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SheltrConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Crea un termostato per ogni canale di tipo `thermostat`."""
    async_setup_channel_entities(
        entry.runtime_data,
        entry,
        async_add_entities,
        (KIND_THERMOSTAT,),
        SheltrClimate,
    )


class SheltrClimate(SheltrEntity, ClimateEntity):
    """Termostato: stagione inverno/estate mappata su riscaldamento/raffrescamento."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL]
    _attr_min_temp = THERMOSTAT_MIN_TEMP
    _attr_max_temp = THERMOSTAT_MAX_TEMP
    _attr_target_temperature_step = THERMOSTAT_TEMP_STEP
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _enable_turn_on_off_backwards_compatibility = False

    @property
    def current_temperature(self) -> float | None:
        """Temperatura misurata dalla sonda del modulo."""
        value = self.channel.get("temperature")
        return float(value) if isinstance(value, (int, float)) else None

    @property
    def target_temperature(self) -> float | None:
        """Setpoint impostato sul modulo."""
        value = self.channel.get("setpoint")
        return float(value) if isinstance(value, (int, float)) else None

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Spento, oppure riscaldamento (inverno) / raffrescamento (estate)."""
        if self.channel.get("isOn") is False:
            return HVACMode.OFF
        if self.channel.get("mode") == MODE_SUMMER:
            return HVACMode.COOL
        return HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction | None:
        """Relè del termostato attivo o a riposo."""
        if self.channel.get("isOn") is False:
            return HVACAction.OFF
        is_active = self.channel.get("isActive")
        if not isinstance(is_active, bool):
            return None
        if not is_active:
            return HVACAction.IDLE
        return HVACAction.COOLING if self.channel.get("mode") == MODE_SUMMER else HVACAction.HEATING

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Imposta il setpoint (accende il termostato se spento)."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        await self.coordinator.async_thermostat_command(
            self._channel_id, setpoint=float(temperature)
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Cambia stagione o spegne il termostato."""
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.async_thermostat_command(self._channel_id, power=False)
            return
        mode = MODE_SUMMER if hvac_mode == HVACMode.COOL else MODE_WINTER
        await self.coordinator.async_thermostat_command(self._channel_id, mode=mode, power=True)

    async def async_turn_on(self) -> None:
        """Accende il termostato mantenendo la stagione corrente."""
        await self.coordinator.async_thermostat_command(self._channel_id, power=True)

    async def async_turn_off(self) -> None:
        """Spegne il termostato (setpoint a 0 sul modulo)."""
        await self.coordinator.async_thermostat_command(self._channel_id, power=False)
