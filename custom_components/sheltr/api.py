"""Client delle API di Smart Domo Cerebro (token dell'impianto o personale, `Authorization: Bearer`)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import json
import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = 20


class SheltrError(Exception):
    """Errore generico verso il portale."""


class SheltrAuthError(SheltrError):
    """Token non valido o revocato."""


class SheltrClient:
    """Le API del portale usate dall'integrazione."""

    def __init__(self, session: aiohttp.ClientSession, url: str, token: str) -> None:
        """Client per un portale (`https://cloud.example.com`) con un token."""
        self._session = session
        self._url = url.rstrip("/")
        self._token = token

    @property
    def url(self) -> str:
        """Indirizzo del portale, senza barra finale."""
        return self._url

    async def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        """Chiamata JSON; 401 (o 403 su `/api/me`) vuol dire token non valido o revocato."""
        headers = {"Authorization": f"Bearer {self._token}", "Accept": "application/json"}
        try:
            async with self._session.request(
                method,
                self._url + path,
                json=body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as response:
                text = await response.text()
                data = json.loads(text) if text else None
                if response.status == 401 or (
                    response.status == 403 and path.startswith("/api/me")
                ):
                    raise SheltrAuthError("Token non valido")
                if response.status >= 400:
                    message = data.get("error") if isinstance(data, dict) else text
                    raise SheltrError(f"HTTP {response.status}: {message}")
                return data
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise SheltrError(f"Portale non raggiungibile: {err}") from err

    async def me(self) -> dict[str, Any]:
        """Chi è il token (con un token dell'impianto: "API · <impianto>")."""
        return await self.request("GET", "/api/me")

    async def homes(self) -> list[dict[str, Any]]:
        """Impianti visibili col token."""
        return await self.request("GET", "/api/homes")

    async def home(self, home_id: str) -> dict[str, Any]:
        """Dettaglio di un impianto: dispositivi, canali con lo stato, sequenze, ingressi."""
        return await self.request("GET", f"/api/homes/{home_id}")

    async def command(self, channel_id: int, body: dict[str, Any]) -> dict[str, Any]:
        """Comando a un canale (`{"action": "on"}`, `{"setpoint": 21.5}`...)."""
        return await self.request("POST", f"/api/channels/{channel_id}/command", body)

    async def run_sequence(self, sequence_id: int) -> None:
        """Avvia una sequenza di un gateway ESP."""
        await self.request("POST", f"/api/sequences/{sequence_id}/run", {})

    async def listen(
        self,
        home_ids: list[str],
        on_event: Callable[[str, dict[str, Any]], Awaitable[None] | None],
        on_connected: Callable[[bool], None],
    ) -> None:
        """Ascolta gli aggiornamenti (Mercure, Server-Sent Events) finché non viene annullato."""
        backoff = 2
        while True:
            try:
                realtime = await self.request("GET", "/api/me/realtime?homes=" + ",".join(home_ids))
                params: list[tuple[str, str]] = [("topic", topic) for topic in realtime["topics"]]
                params.append(("authorization", realtime["token"]))
                hub = realtime["hubUrl"]
                if hub.startswith("/"):
                    hub = self._url + hub
                ttl = max(60, int(realtime.get("expiresIn", 3600)) - 120)
                timeout = aiohttp.ClientTimeout(total=ttl, sock_read=90)
                async with self._session.get(hub, params=params, timeout=timeout) as response:
                    if response.status != 200:
                        raise SheltrError(f"Hub in tempo reale: HTTP {response.status}")
                    on_connected(True)
                    backoff = 2
                    await self._read_events(response, on_event)
            except asyncio.CancelledError:
                raise
            except TimeoutError:
                # Token in scadenza (o linea muta): ci si ricollega con un token nuovo.
                pass
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Collegamento in tempo reale interrotto: %s", err)
            on_connected(False)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)

    @staticmethod
    async def _read_events(
        response: aiohttp.ClientResponse,
        on_event: Callable[[str, dict[str, Any]], Awaitable[None] | None],
    ) -> None:
        """Righe `data:` di un flusso SSE: ogni evento è un JSON `{"type", "data"}`."""
        data_lines: list[str] = []
        async for raw in response.content:
            line = raw.decode("utf-8", errors="ignore").rstrip("\r\n")
            if line.startswith("data:"):
                data_lines.append(line[5:].lstrip())
            elif line == "" and data_lines:
                payload = "\n".join(data_lines)
                data_lines = []
                try:
                    event = json.loads(payload)
                except ValueError:
                    continue
                result = on_event(event.get("type", ""), event.get("data") or {})
                if asyncio.iscoroutine(result):
                    await result
