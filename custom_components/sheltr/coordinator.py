"""Stato degli impianti: una lettura completa all'avvio, poi aggiornamenti in tempo reale."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SheltrAuthError, SheltrClient, SheltrError
from .const import DOMAIN, SCAN_INTERVAL_SECONDS
from .devices import device_info

_LOGGER = logging.getLogger(__name__)


class SheltrCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """data = {id impianto: dettaglio come lo restituisce `/api/homes/<id>`}."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: SheltrClient) -> None:
        """Coordinatore di un token (uno o più impianti)."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL_SECONDS),
        )
        self.client = client
        self.realtime = False
        self._listener: asyncio.Task | None = None
        self._refresh_handle: asyncio.TimerHandle | None = None

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Rilegge tutti gli impianti del token."""
        try:
            homes = await self.client.homes()
            details = await asyncio.gather(*(self.client.home(home["id"]) for home in homes))
        except SheltrAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except SheltrError as err:
            raise UpdateFailed(str(err)) from err
        return {home["id"]: home for home in details}

    def start_listening(self) -> None:
        """Apre il collegamento in tempo reale (in background)."""
        if self._listener is None and self.data:
            self._listener = self.hass.async_create_background_task(
                self.client.listen(list(self.data), self.handle_event, self._on_connected),
                "sheltr-realtime",
            )

    async def stop_listening(self) -> None:
        """Chiude il collegamento in tempo reale."""
        if self._refresh_handle is not None:
            self._refresh_handle.cancel()
            self._refresh_handle = None
        if self._listener is not None:
            self._listener.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._listener
            self._listener = None

    def _on_connected(self, connected: bool) -> None:
        self.realtime = connected

    def _schedule_refresh(self) -> None:
        if self._refresh_handle is not None:
            self._refresh_handle.cancel()
        self._refresh_handle = self.hass.loop.call_later(
            0.5, lambda: self.hass.async_create_task(self.async_request_refresh())
        )

    def handle_event(self, kind: str, data: dict[str, Any]) -> None:
        """Applica un evento del portale: stato, dispositivo, ingresso o configurazione."""
        if not self.data:
            return
        if kind == "state":
            updates = {item["channelId"]: item["state"] for item in data.get("channels", [])}
            for home in self.data.values():
                for channel in home["channels"]:
                    if channel["id"] in updates:
                        channel["state"] = updates[channel["id"]]
            self.async_set_updated_data(self.data)
        elif kind == "device":
            for home in self.data.values():
                for device in home["devices"]:
                    if device["id"] == data.get("id"):
                        device["online"] = bool(data.get("online"))
                for channel in home["channels"]:
                    if channel["deviceId"] == data.get("id"):
                        channel["online"] = bool(data.get("online"))
            self.async_set_updated_data(self.data)
        elif kind == "input":
            for home in self.data.values():
                for item in home["inputs"]:
                    if item["id"] == data.get("inputId"):
                        item["active"] = bool(data.get("active"))
            self.async_set_updated_data(self.data)
        elif kind == "config":
            # Moduli o nomi cambiati: si rilegge tutto (una volta sola per raffica).
            self._schedule_refresh()

    def gateway(self, home: dict[str, Any], device: dict[str, Any]) -> str | None:
        """Il gateway nel registro dei dispositivi (creato se manca): i moduli vi si collegano."""
        if self.config_entry is None:
            return None
        entry = dr.async_get(self.hass).async_get_or_create(
            config_entry_id=self.config_entry.entry_id, **device_info(home, device)
        )
        return entry.id

    def find(self, collection: str, item_id: int) -> dict[str, Any] | None:
        """Un canale, una sequenza o un ingresso per id."""
        for home in (self.data or {}).values():
            for item in home[collection]:
                if item["id"] == item_id:
                    return item
        return None
