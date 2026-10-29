"""Termostati: setpoint a mezzi gradi, stagione inverno (riscalda) / estate (raffresca)."""

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

from . import SheltrConfigEntry
from .entity import SheltrEntity, channels


async def async_setup_entry(
    hass: HomeAssistant, entry: SheltrConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Un termostato per ogni canale termostato."""
    coordinator = entry.runtime_data
    async_add_entities(
        SheltrThermostat(coordinator, "channels", c) for c in channels(coordinator, "thermostat")
    )


class SheltrThermostat(SheltrEntity, ClimateEntity):
    """Termostato: inverno = riscaldamento, estate = raffrescamento, spento = setpoint 0."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_min_temp = 5
    _attr_max_temp = 30
    _attr_target_temperature_step = 0.5

    @property
    def _state(self) -> dict[str, Any]:
        item = self.item
        return {} if item is None else item["state"]

    @property
    def current_temperature(self) -> float | None:
        """Temperatura letta dal modulo."""
        return self._state.get("temperature")

    @property
    def target_temperature(self) -> float | None:
        """Setpoint."""
        return self._state.get("setpoint")

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Spento, oppure la stagione."""
        state = self._state
        if state.get("isOn") is False:
            return HVACMode.OFF
        return HVACMode.COOL if state.get("mode") == "summer" else HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction | None:
        """Dal relè del modulo: lavora o è fermo."""
        state = self._state
        if state.get("isOn") is False:
            return HVACAction.OFF
        if state.get("active") is None:
            return None
        if not state["active"]:
            return HVACAction.IDLE
        return HVACAction.COOLING if state.get("mode") == "summer" else HVACAction.HEATING

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Nuovo setpoint (il portale lo arrotonda al mezzo grado)."""
        if ATTR_TEMPERATURE in kwargs:
            await self.coordinator.client.command(
                self._item_id, {"setpoint": float(kwargs[ATTR_TEMPERATURE])}
            )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Stagione (riaccendendolo se era spento) oppure spento."""
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.client.command(self._item_id, {"action": "off"})
            return
        body: dict[str, Any] = {"mode": "summer" if hvac_mode == HVACMode.COOL else "winter"}
        if self._state.get("isOn") is False:
            body["action"] = "on"
        await self.coordinator.client.command(self._item_id, body)

    async def async_turn_on(self) -> None:
        """Riaccende all'ultimo setpoint."""
        await self.coordinator.client.command(self._item_id, {"action": "on"})

    async def async_turn_off(self) -> None:
        """Spegne."""
        await self.coordinator.client.command(self._item_id, {"action": "off"})
