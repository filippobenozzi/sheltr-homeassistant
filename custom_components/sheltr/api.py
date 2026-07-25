"""Client asincrono per le API di Sheltr Cloud."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 20
COMMAND_TIMEOUT = 60
REFRESH_TIMEOUT = 120


class SheltrError(Exception):
    """Errore generico restituito dal portale Sheltr."""


class SheltrConnectionError(SheltrError):
    """Il portale non è raggiungibile."""


class SheltrAuthError(SheltrError):
    """Token o credenziali non validi per l'istanza."""


class SheltrNotFoundError(SheltrError):
    """Istanza o dispositivo inesistente."""


def normalize_base_url(raw: str) -> str:
    """Normalizza l'URL del portale (`http://host:8080`, senza slash finale)."""
    text = (raw or "").strip().rstrip("/")
    if not text:
        raise ValueError("URL vuoto")
    if "://" not in text:
        text = f"http://{text}"
    return text


def _error_message(data: Any, fallback: str) -> str:
    if isinstance(data, dict):
        message = data.get("error")
        if isinstance(message, str) and message.strip():
            return message.strip()
    return fallback


class SheltrClient:
    """Wrapper sulle rotte `/api/instances/<id>/...` del portale."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        instance_id: str,
        *,
        token: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        """Inizializza il client con token e/o credenziali istanza."""
        self._session = session
        self._base_url = normalize_base_url(base_url)
        self._instance_id = instance_id.strip()
        self._token = (token or "").strip() or None
        self._username = (username or "").strip() or None
        self._password = password or None
        self._login_lock = asyncio.Lock()

    @property
    def base_url(self) -> str:
        """URL base del portale."""
        return self._base_url

    @property
    def instance_id(self) -> str:
        """ID dell'impianto (istanza) gestito da questo client."""
        return self._instance_id

    @property
    def token(self) -> str | None:
        """Token istanza attualmente in uso."""
        return self._token

    @property
    def can_relogin(self) -> bool:
        """Indica se il client può rinnovare da solo il token scaduto."""
        return bool(self._username and self._password)

    @property
    def control_url(self) -> str:
        """URL della UI di controllo dell'istanza."""
        return f"{self._base_url}/control/{self._instance_id}"

    async def _read_json(self, response: aiohttp.ClientResponse) -> Any:
        try:
            return await response.json(content_type=None)
        except (aiohttp.ContentTypeError, ValueError):
            return None

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        timeout: int = DEFAULT_TIMEOUT,
        authenticate: bool = True,
        retry_auth: bool = True,
    ) -> Any:
        url = f"{self._base_url}{path}"
        headers: dict[str, str] = {}
        if authenticate and self._token:
            headers["X-Instance-Token"] = self._token

        try:
            async with self._session.request(
                method,
                url,
                params=params,
                json=json,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as response:
                data = await self._read_json(response)
                status = response.status
        except TimeoutError as err:
            raise SheltrConnectionError(f"Timeout nella richiesta a {url}") from err
        except aiohttp.ClientError as err:
            raise SheltrConnectionError(f"Errore di connessione a {url}: {err}") from err

        if status in (401, 403):
            if authenticate and retry_auth and self.can_relogin:
                # Il token istanza ha vita limitata (INSTANCE_AUTH_TTL_SEC): rinnovalo e riprova.
                _LOGGER.debug("Token istanza scaduto, nuovo login su %s", self._instance_id)
                await self.async_login()
                return await self._request(
                    method,
                    path,
                    params=params,
                    json=json,
                    timeout=timeout,
                    authenticate=authenticate,
                    retry_auth=False,
                )
            raise SheltrAuthError(_error_message(data, "Autenticazione non valida"))

        if status == 404:
            raise SheltrNotFoundError(_error_message(data, "Risorsa non trovata"))

        if status >= 400:
            raise SheltrError(_error_message(data, f"Errore HTTP {status}"))

        return data

    async def async_login(self) -> str:
        """Esegue il login istanza e memorizza il nuovo token."""
        if not self.can_relogin:
            raise SheltrAuthError("Username e password non configurati")

        token_before = self._token
        async with self._login_lock:
            if self._token is not None and self._token != token_before:
                # Un'altra richiesta ha già rinnovato il token mentre attendevamo il lock.
                return self._token

            data = await self._request(
                "POST",
                f"/api/instances/{self._instance_id}/auth/login",
                json={"username": self._username, "password": self._password},
                authenticate=False,
            )
            token = (data or {}).get("token") if isinstance(data, dict) else None
            if not isinstance(token, str) or not token:
                raise SheltrAuthError("Il portale non ha restituito un token valido")
            self._token = token
            return token

    async def async_ensure_token(self) -> None:
        """Garantisce di avere un token utilizzabile (login se necessario)."""
        if self._token:
            return
        await self.async_login()

    async def async_get_instance(self) -> dict[str, Any]:
        """Legge la configurazione dell'istanza (nome, tipo dispositivo, schede)."""
        data = await self._request("GET", f"/api/instances/{self._instance_id}")
        instance = (data or {}).get("instance") if isinstance(data, dict) else None
        if not isinstance(instance, dict):
            raise SheltrError("Risposta inattesa dal portale per l'istanza")
        if instance.get("restricted"):
            # Il portale risponde con la vista minimale quando il token non è valido.
            raise SheltrAuthError("Token istanza non valido o permessi insufficienti")
        return instance

    async def async_get_status(self, *, refresh: bool = False) -> dict[str, Any]:
        """Legge lo stato per stanze; con `refresh` esegue il polling dei moduli."""
        data = await self._request(
            "GET",
            f"/api/instances/{self._instance_id}/status",
            params={"refresh": "1"} if refresh else None,
            timeout=REFRESH_TIMEOUT if refresh else DEFAULT_TIMEOUT,
        )
        if not isinstance(data, dict):
            raise SheltrError("Risposta inattesa dal portale per lo stato")
        return data

    async def async_poll_device(self, channel_id: str) -> dict[str, Any]:
        """Polling mirato del modulo che ospita il canale indicato."""
        data = await self._request(
            "POST",
            f"/api/instances/{self._instance_id}/poll",
            json={"channelId": channel_id},
            timeout=COMMAND_TIMEOUT,
        )
        if not isinstance(data, dict):
            raise SheltrError("Risposta inattesa dal portale per il polling")
        return data

    async def _async_command(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = await self._request(
            "POST",
            f"/api/instances/{self._instance_id}/{path}",
            json=payload,
            timeout=COMMAND_TIMEOUT,
        )
        if not isinstance(data, dict):
            raise SheltrError("Risposta inattesa dal portale per il comando")
        return data

    async def async_light_command(self, light_id: str, action: str) -> dict[str, Any]:
        """Comanda una luce (`on`/`off`)."""
        return await self._async_command("lights/command", {"lightId": light_id, "action": action})

    async def async_dimmer_command(
        self, dimmer_id: str, action: str, level: int | None = None
    ) -> dict[str, Any]:
        """Comanda un dimmer (`on`/`off`/`toggle`/`set` con livello 0..9)."""
        payload: dict[str, Any] = {"dimmerId": dimmer_id, "action": action}
        if level is not None:
            payload["level"] = level
        return await self._async_command("dimmers/command", payload)

    async def async_shutter_command(self, shutter_id: str, action: str) -> dict[str, Any]:
        """Comanda una tapparella (`up`/`down`/`stop`)."""
        return await self._async_command(
            "shutters/command", {"shutterId": shutter_id, "action": action}
        )

    async def async_thermostat_command(
        self,
        thermostat_id: str,
        *,
        setpoint: float | None = None,
        mode: str | None = None,
        power: bool | None = None,
    ) -> dict[str, Any]:
        """Comanda un termostato (setpoint, stagione, accensione)."""
        payload: dict[str, Any] = {"thermostatId": thermostat_id}
        if setpoint is not None:
            payload["setpoint"] = setpoint
        if mode is not None:
            payload["mode"] = mode
        if power is not None:
            payload["power"] = power
        return await self._async_command("thermostats/command", payload)
