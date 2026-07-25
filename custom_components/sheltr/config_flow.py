"""Flusso di configurazione dell'integrazione Sheltr Cloud."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import (
    SheltrAuthError,
    SheltrClient,
    SheltrConnectionError,
    SheltrError,
    SheltrNotFoundError,
    normalize_base_url,
)
from .const import (
    CONF_ACTIVE_POLL_INTERVAL,
    CONF_INSTANCE_ID,
    CONF_POLL_AFTER_COMMAND,
    DEFAULT_ACTIVE_POLL_INTERVAL,
    DEFAULT_POLL_AFTER_COMMAND,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)
from .coordinator import SheltrConfigEntry

_LOGGER = logging.getLogger(__name__)

PASSWORD_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


class MissingAuth(Exception):
    """Nessuna credenziale né token forniti."""


def _connection_schema(defaults: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_URL, default=defaults.get(CONF_URL, "")): TextSelector(
                TextSelectorConfig(type=TextSelectorType.URL)
            ),
            vol.Required(
                CONF_INSTANCE_ID, default=defaults.get(CONF_INSTANCE_ID, "")
            ): TextSelector(),
            vol.Optional(CONF_USERNAME, default=defaults.get(CONF_USERNAME, "")): TextSelector(),
            vol.Optional(CONF_PASSWORD, default=defaults.get(CONF_PASSWORD, "")): PASSWORD_SELECTOR,
            vol.Optional(CONF_TOKEN, default=defaults.get(CONF_TOKEN, "")): PASSWORD_SELECTOR,
            vol.Optional(
                CONF_VERIFY_SSL, default=defaults.get(CONF_VERIFY_SSL, True)
            ): BooleanSelector(),
        }
    )


def _credentials_schema(defaults: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(CONF_USERNAME, default=defaults.get(CONF_USERNAME, "")): TextSelector(),
            vol.Optional(CONF_PASSWORD, default=""): PASSWORD_SELECTOR,
            vol.Optional(CONF_TOKEN, default=""): PASSWORD_SELECTOR,
        }
    )


def _clean(user_input: Mapping[str, Any]) -> dict[str, Any]:
    """Ripulisce l'input rimuovendo i campi opzionali lasciati vuoti."""
    data: dict[str, Any] = {}
    for key, value in user_input.items():
        if isinstance(value, str):
            value = value.strip()
            if not value:
                continue
        data[key] = value
    return data


async def _async_validate(hass: HomeAssistant, data: Mapping[str, Any]) -> dict[str, Any]:
    """Verifica URL, credenziali e ID impianto; restituisce l'istanza."""
    session = async_get_clientsession(hass, verify_ssl=data.get(CONF_VERIFY_SSL, True))
    client = SheltrClient(
        session,
        data[CONF_URL],
        data[CONF_INSTANCE_ID],
        token=data.get(CONF_TOKEN),
        username=data.get(CONF_USERNAME),
        password=data.get(CONF_PASSWORD),
    )

    if client.can_relogin:
        await client.async_login()
    elif not client.token:
        raise MissingAuth

    return await client.async_get_instance()


class SheltrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configura l'accesso a un impianto Sheltr Cloud."""

    VERSION = 1

    async def _async_try(
        self, user_input: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, dict[str, str]]:
        """Valida l'input e traduce le eccezioni in errori del form."""
        errors: dict[str, str] = {}
        try:
            instance = await _async_validate(self.hass, user_input)
        except MissingAuth:
            errors["base"] = "missing_auth"
        except SheltrAuthError:
            errors["base"] = "invalid_auth"
        except SheltrNotFoundError:
            errors["base"] = "instance_not_found"
        except SheltrConnectionError:
            errors["base"] = "cannot_connect"
        except (SheltrError, ValueError):
            errors["base"] = "unknown"
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Errore imprevisto durante la configurazione di Sheltr")
            errors["base"] = "unknown"
        else:
            return instance, errors
        return None, errors

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Primo passo: dati del portale, ID impianto e autenticazione."""
        errors: dict[str, str] = {}
        data: dict[str, Any] = {}

        if user_input is not None:
            data = _clean(user_input)
            instance, errors = await self._async_try(data)
            if instance is not None:
                await self.async_set_unique_id(_unique_id(data))
                self._abort_if_unique_id_configured()
                data[CONF_URL] = normalize_base_url(data[CONF_URL])
                return self.async_create_entry(
                    title=instance.get("name") or data[CONF_INSTANCE_ID],
                    data=data,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_connection_schema(data or {CONF_URL: "http://"}),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Il token è scaduto o non è più valido: chiedi nuove credenziali."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Aggiorna credenziali o token della voce esistente."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            # I campi di autenticazione vengono sostituiti in blocco: chi passa solo il
            # token perde le vecchie credenziali e viceversa.
            data = {
                key: value
                for key, value in entry.data.items()
                if key not in (CONF_USERNAME, CONF_PASSWORD, CONF_TOKEN)
            }
            data.update(_clean(user_input))
            instance, errors = await self._async_try(data)
            if instance is not None:
                return self.async_update_reload_and_abort(entry, data=data)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=_credentials_schema(entry.data),
            errors=errors,
            description_placeholders={"instance_id": entry.data.get(CONF_INSTANCE_ID, "")},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Permette di cambiare URL del portale, impianto o autenticazione."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        data: dict[str, Any] = dict(entry.data)

        if user_input is not None:
            data = _clean(user_input)
            instance, errors = await self._async_try(data)
            if instance is not None:
                await self.async_set_unique_id(_unique_id(data))
                self._abort_if_unique_id_mismatch(reason="wrong_instance")
                data[CONF_URL] = normalize_base_url(data[CONF_URL])
                return self.async_update_reload_and_abort(entry, data=data)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_connection_schema(data),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: SheltrConfigEntry) -> SheltrOptionsFlow:
        """Espone le opzioni di polling."""
        return SheltrOptionsFlow()


def _unique_id(data: Mapping[str, Any]) -> str:
    """Identificativo univoco: portale + impianto."""
    return f"{normalize_base_url(data[CONF_URL])}::{data[CONF_INSTANCE_ID]}"


class SheltrOptionsFlow(OptionsFlow):
    """Opzioni di aggiornamento dell'impianto."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Imposta intervalli di lettura e verifica dei comandi."""
        if user_input is not None:
            return self.async_create_entry(
                data={
                    CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                    CONF_ACTIVE_POLL_INTERVAL: int(user_input[CONF_ACTIVE_POLL_INTERVAL]),
                    CONF_POLL_AFTER_COMMAND: bool(user_input[CONF_POLL_AFTER_COMMAND]),
                }
            )

        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL,
                        max=3600,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement="s",
                    )
                ),
                vol.Required(
                    CONF_ACTIVE_POLL_INTERVAL,
                    default=options.get(CONF_ACTIVE_POLL_INTERVAL, DEFAULT_ACTIVE_POLL_INTERVAL),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=0,
                        max=86400,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement="s",
                    )
                ),
                vol.Required(
                    CONF_POLL_AFTER_COMMAND,
                    default=options.get(CONF_POLL_AFTER_COMMAND, DEFAULT_POLL_AFTER_COMMAND),
                ): BooleanSelector(),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
