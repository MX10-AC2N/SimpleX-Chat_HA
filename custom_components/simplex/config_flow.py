"""Config flow for SimpleX Chat."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from urllib.parse import urlparse

from aiohttp import ClientError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, OptionsFlowWithReload
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_TARGETS,
    CONF_WS_URL,
    DEFAULT_WS_URL,
    DOMAIN,
    ERROR_ALIAS_EXISTS,
    ERROR_CANNOT_CONNECT,
    ERROR_INVITE_FAILED,
    ERROR_INVALID_LINK,
    ERROR_TIMEOUT,
    ERROR_WS_NOT_CONNECTED,
)
from .websocket_client import (
    SimplexWsClient,
    SimplexWsError,
    SimplexWsTimeoutError,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_WS_URL, default=DEFAULT_WS_URL): str,
    }
)


async def _validate_ws(hass: HomeAssistant, ws_url: str) -> None:
    client = SimplexWsClient(ws_url, hass.loop)
    try:
        await client.connect()
        # Optional: verify we can talk to the CLI
        await client.get_active_user()
    finally:
        await client.close()


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SimpleX Chat."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            ws_url = user_input.get(CONF_WS_URL, DEFAULT_WS_URL).strip()
            try:
                await _validate_ws(self.hass, ws_url)
            except Exception:  # noqa: BLE001
                errors["base"] = ERROR_CANNOT_CONNECT
            else:
                await self.async_set_unique_id(ws_url)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="SimpleX Chat",
                    data={CONF_WS_URL: ws_url},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlowHandler:
        return OptionsFlowHandler()


class OptionsFlowHandler(OptionsFlowWithReload):
    """Handle options (add / remove contacts)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options=["add_contact", "remove_contact", "show_targets"],
        )

    async def async_step_add_contact(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            alias = user_input["alias"].strip()
            link = user_input["invite_link"].strip()

            if not alias:
                errors["alias"] = "required"
            elif not link:
                errors["invite_link"] = "required"
            else:
                # Soft check only — many valid relays use smp*.simplex.im /i#…
                if not _looks_like_simplex_link(link):
                    errors["base"] = ERROR_INVALID_LINK
                else:
                    current = dict(self.config_entry.options.get(CONF_TARGETS, {}))
                    if alias in current:
                        errors["alias"] = ERROR_ALIAS_EXISTS
                    else:
                        result = await self._accept_invite(alias, link)
                        if isinstance(result, str):
                            errors["base"] = result
                        else:
                            return result

        return self.async_show_form(
            step_id="add_contact",
            data_schema=vol.Schema(
                {
                    vol.Required("alias"): str,
                    vol.Required("invite_link"): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "hint": "Paste a SimpleX invitation or contact address link."
            },
        )

    async def async_step_remove_contact(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        current = dict(self.config_entry.options.get(CONF_TARGETS, {}))
        if not current:
            return self.async_abort(reason="no_targets")

        if user_input is not None:
            to_remove = user_input.get("alias")
            if to_remove in current:
                del current[to_remove]
                return self.async_create_entry(
                    title="", data={CONF_TARGETS: current}
                )

        return self.async_show_form(
            step_id="remove_contact",
            data_schema=vol.Schema(
                {
                    vol.Required("alias"): vol.In(list(current.keys())),
                }
            ),
        )

    async def async_step_show_targets(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        current = self.config_entry.options.get(CONF_TARGETS, {})
        lines = [
            f"• **{data.get('name', alias)}** → `{data.get('chat_ref', '?')}`"
            for alias, data in current.items()
        ] or ["*(aucun contact configuré)*"]
        return self.async_show_form(
            step_id="show_targets",
            data_schema=vol.Schema({}),
            description_placeholders={"targets": "\n".join(lines)},
        )

    # ------------------------------------------------------------------

    async def _accept_invite(self, alias: str, link: str) -> FlowResult | str:
        """Try to accept the invite. Returns a FlowResult on success or an error key."""
        client: SimplexWsClient | None = None
        temporary = False

        domain_data = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        if domain_data and (c := domain_data.get("client")):
            client = c
        else:
            ws_url = self.config_entry.data.get(CONF_WS_URL, DEFAULT_WS_URL)
            client = SimplexWsClient(ws_url, self.hass.loop)
            temporary = True
            try:
                await client.connect()
            except (ClientError, asyncio.TimeoutError, OSError):
                return ERROR_WS_NOT_CONNECTED

        try:
            resp = await client.accept_invite_link(link, timeout=60.0)
            chat_ref = resp.get("chat_ref")
            if not chat_ref:
                return ERROR_INVITE_FAILED

            current = dict(self.config_entry.options.get(CONF_TARGETS, {}))
            current[alias] = {
                "chat_ref": chat_ref,
                "name": alias,
                "type": resp.get("type", "contact"),
            }
            return self.async_create_entry(
                title="", data={CONF_TARGETS: current}
            )
        except SimplexWsTimeoutError as err:
            _LOGGER.warning("Invite timeout: %s payload=%s", err, getattr(err, "payload", None))
            return ERROR_TIMEOUT
        except SimplexWsError as err:
            reason = (err.reason or "")
            message = (err.message or "")
            combined = f"{reason} {message}".lower()
            _LOGGER.warning(
                "Invite failed: reason=%s message=%s payload=%s",
                reason,
                message,
                getattr(err, "payload", None),
            )
            # Only map clearly expired/revoked — never label a CLI/network failure as "invalid link"
            if any(k in combined for k in ("expired", "revoked")):
                return "invite_expired"
            return ERROR_INVITE_FAILED
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected error accepting invite")
            return "unknown"
        finally:
            if temporary and client is not None:
                await client.close()