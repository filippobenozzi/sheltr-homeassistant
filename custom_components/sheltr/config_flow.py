"""Configurazione da interfaccia: indirizzo del portale e token."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SheltrAuthError, SheltrClient, SheltrError
from .const import CONF_TOKEN, CONF_URL, DOMAIN

SCHEMA = vol.Schema({vol.Required(CONF_URL): str, vol.Required(CONF_TOKEN): str})


def normalize_url(raw: str) -> str:
    """`cloud.example.com/` → `https://cloud.example.com`."""
    url = raw.strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


class SheltrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Indirizzo del portale e un token: dell'impianto (API dell'impianto) o personale."""

    VERSION = 2

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Chiede indirizzo e token e li prova su `/api/me`."""
        errors: dict[str, str] = {}
        if user_input is not None:
            url = normalize_url(user_input[CONF_URL])
            token = user_input[CONF_TOKEN].strip()
            client = SheltrClient(async_get_clientsession(self.hass), url, token)
            try:
                me = await client.me()
            except SheltrAuthError:
                errors["base"] = "invalid_auth"
            except SheltrError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(f"{url}|{me['id']}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Smart Domo Cerebro ({me['name']})",
                    data={CONF_URL: url, CONF_TOKEN: token},
                )
        return self.async_show_form(step_id="user", data_schema=SCHEMA, errors=errors)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Token revocato o rigenerato: se ne chiede uno nuovo."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Nuovo token per la stessa voce."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            token = user_input[CONF_TOKEN].strip()
            client = SheltrClient(async_get_clientsession(self.hass), entry.data[CONF_URL], token)
            try:
                await client.me()
            except SheltrAuthError:
                errors["base"] = "invalid_auth"
            except SheltrError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(entry, data_updates={CONF_TOKEN: token})
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_TOKEN): str}),
            errors=errors,
        )
