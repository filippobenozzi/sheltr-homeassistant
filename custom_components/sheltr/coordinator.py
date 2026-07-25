"""Coordinator che tiene allineato Home Assistant con lo stato dell'impianto."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SheltrAuthError, SheltrClient, SheltrError
from .const import (
    CONF_ACTIVE_POLL_INTERVAL,
    CONF_POLL_AFTER_COMMAND,
    DEFAULT_ACTIVE_POLL_INTERVAL,
    DEFAULT_POLL_AFTER_COMMAND,
    DEFAULT_ROOM,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    KIND_COLLECTIONS,
)

_LOGGER = logging.getLogger(__name__)

type SheltrConfigEntry = ConfigEntry[SheltrCoordinator]


@dataclass(slots=True)
class SheltrData:
    """Fotografia dell'impianto usata dalle entità."""

    channels: dict[str, dict[str, Any]] = field(default_factory=dict)
    boards: dict[str, dict[str, Any]] = field(default_factory=dict)
    online: bool | None = None
    last_seen: str | None = None
    heartbeat_minutes: int = 0
    data_saver: bool = False
    updated_at: str | None = None
    refresh_errors: list[dict[str, Any]] = field(default_factory=list)


class SheltrCoordinator(DataUpdateCoordinator[SheltrData]):
    """Legge `/status` e inoltra i comandi alle rotte del portale."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: SheltrConfigEntry,
        client: SheltrClient,
    ) -> None:
        """Configura il polling in base alle opzioni della voce di configurazione."""
        self.client = client
        self.instance: dict[str, Any] = {}
        self._last_active_poll: float | None = None
        self._force_active_poll = False

        scan_interval = int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {client.instance_id}",
            update_interval=timedelta(seconds=scan_interval),
        )

    @property
    def instance_id(self) -> str:
        """ID dell'impianto."""
        return self.client.instance_id

    @property
    def instance_name(self) -> str:
        """Nome leggibile dell'impianto."""
        name = self.instance.get("name")
        return name if isinstance(name, str) and name.strip() else self.instance_id

    @property
    def active_poll_interval(self) -> int:
        """Intervallo (secondi) del polling attivo dei moduli; 0 = disattivato."""
        entry = self.config_entry
        if entry is None:
            return DEFAULT_ACTIVE_POLL_INTERVAL
        return int(entry.options.get(CONF_ACTIVE_POLL_INTERVAL, DEFAULT_ACTIVE_POLL_INTERVAL))

    @property
    def poll_after_command(self) -> bool:
        """Verifica sul campo lo stato del modulo dopo ogni comando."""
        entry = self.config_entry
        if entry is None:
            return DEFAULT_POLL_AFTER_COMMAND
        return bool(entry.options.get(CONF_POLL_AFTER_COMMAND, DEFAULT_POLL_AFTER_COMMAND))

    async def async_load_instance(self) -> None:
        """Carica la configurazione dell'istanza (nome, tipo dispositivo, schede)."""
        try:
            self.instance = await self.client.async_get_instance()
        except SheltrAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err

    async def async_force_active_poll(self) -> None:
        """Forza un polling attivo dei moduli al prossimo aggiornamento (immediato)."""
        self._force_active_poll = True
        await self.async_refresh()

    def _should_active_poll(self) -> bool:
        if self._force_active_poll:
            return True
        interval = self.active_poll_interval
        if interval <= 0:
            return False
        if self._last_active_poll is None:
            # Al primo aggiornamento ci si accontenta dello stato già noto al portale,
            # così il setup non resta bloccato sul polling MQTT di tutti i moduli.
            return self.data is not None
        return (time.monotonic() - self._last_active_poll) >= interval

    async def _async_update_data(self) -> SheltrData:
        refresh = self._should_active_poll()
        try:
            status = await self.client.async_get_status(refresh=refresh)
        except SheltrAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except SheltrError as err:
            raise UpdateFailed(str(err)) from err

        self._force_active_poll = False
        if refresh and not status.get("refreshSkipped"):
            self._last_active_poll = time.monotonic()

        return _parse_status(status)

    def _apply_status(self, status: dict[str, Any]) -> None:
        """Sostituisce i dati correnti con quelli di una risposta `/status`."""
        self.async_set_updated_data(_parse_status(status))

    def _apply_sent(self, result: dict[str, Any], keys: tuple[str, ...]) -> None:
        """Applica al volo lo stato restituito dal comando, senza attendere il polling."""
        data = self.data
        if data is None:
            return
        sent = result.get("sent")
        if not isinstance(sent, list):
            return
        for item in sent:
            if not isinstance(item, dict):
                continue
            channel_id = item.get("id")
            channel = data.channels.get(channel_id) if isinstance(channel_id, str) else None
            if channel is None:
                continue
            for key in keys:
                if key in item:
                    channel[key] = item[key]
        self.async_set_updated_data(data)

    async def _async_after_command(self, channel_id: str) -> None:
        """Verifica sul campo lo stato del modulo appena comandato, se richiesto."""
        if not self.poll_after_command:
            return
        try:
            status = await self.client.async_poll_device(channel_id)
        except SheltrError as err:
            _LOGGER.debug("Polling di verifica fallito per %s: %s", channel_id, err)
            return
        self._apply_status(status)

    async def _async_run_command(
        self,
        channel_id: str,
        coro: Any,
        keys: tuple[str, ...],
    ) -> None:
        try:
            result = await coro
        except SheltrAuthError as err:
            # Il client ha già provato a rinnovare il token: servono nuove credenziali.
            if self.config_entry is not None:
                self.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(f"Autenticazione Sheltr non valida: {err}") from err
        except SheltrError as err:
            raise HomeAssistantError(f"Comando Sheltr fallito: {err}") from err
        self._apply_sent(result, keys)
        await self._async_after_command(channel_id)

    async def async_light_command(self, channel_id: str, action: str) -> None:
        """Accende o spegne una luce."""
        await self._async_run_command(
            channel_id,
            self.client.async_light_command(channel_id, action),
            ("isOn", "action"),
        )

    async def async_dimmer_command(
        self, channel_id: str, action: str, level: int | None = None
    ) -> None:
        """Comanda un dimmer."""
        await self._async_run_command(
            channel_id,
            self.client.async_dimmer_command(channel_id, action, level),
            ("isOn", "level", "action"),
        )

    async def async_shutter_command(self, channel_id: str, action: str) -> None:
        """Comanda una tapparella."""
        await self._async_run_command(
            channel_id,
            self.client.async_shutter_command(channel_id, action),
            ("action", "isActive"),
        )

    async def async_thermostat_command(
        self,
        channel_id: str,
        *,
        setpoint: float | None = None,
        mode: str | None = None,
        power: bool | None = None,
    ) -> None:
        """Comanda un termostato."""
        await self._async_run_command(
            channel_id,
            self.client.async_thermostat_command(
                channel_id, setpoint=setpoint, mode=mode, power=power
            ),
            ("setpoint", "mode", "isOn", "isActive", "temperature"),
        )


def _parse_status(status: dict[str, Any]) -> SheltrData:
    """Trasforma la risposta `/status` in una mappa canale -> stato."""
    channels: dict[str, dict[str, Any]] = {}

    for room in status.get("rooms", []) or []:
        if not isinstance(room, dict):
            continue
        room_name = room.get("name") or DEFAULT_ROOM
        for kind, collection in KIND_COLLECTIONS.items():
            for item in room.get(collection, []) or []:
                if not isinstance(item, dict):
                    continue
                channel_id = item.get("id")
                if not isinstance(channel_id, str) or not channel_id:
                    continue
                channel = dict(item)
                channel["kind"] = kind
                channel["room"] = channel.get("room") or room_name
                channel["roomColor"] = room.get("color")
                channels[channel_id] = channel

    boards: dict[str, dict[str, Any]] = {}
    for board in status.get("boards", []) or []:
        if not isinstance(board, dict):
            continue
        board_id = board.get("id")
        if isinstance(board_id, str) and board_id:
            boards[board_id] = board

    device = status.get("device") if isinstance(status.get("device"), dict) else {}
    online = device.get("online")
    last_seen = device.get("lastSeenAt")
    refresh_errors = status.get("refreshErrors")

    return SheltrData(
        channels=channels,
        boards=boards,
        online=online if isinstance(online, bool) else None,
        last_seen=last_seen if isinstance(last_seen, str) else None,
        heartbeat_minutes=int(device.get("heartbeatMinutes") or 0),
        data_saver=bool(status.get("dataSaver")),
        updated_at=status.get("updatedAt"),
        refresh_errors=refresh_errors if isinstance(refresh_errors, list) else [],
    )
