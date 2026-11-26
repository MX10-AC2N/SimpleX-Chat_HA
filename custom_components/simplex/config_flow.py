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

from .frontend import DashboardInstallError, async_install_dashboard, available_dashboards
from .const import (
    CONF_AUTO_ACCEPT_FILES,
    CONF_AUTO_DISCOVER,
    CONF_INBOX_DIR,
    CONF_OUTBOX_DIR,
    CONF_TARGETS,
    CONF_WS_URL,
    DEFAULT_AUTO_ACCEPT_FILES,
    DEFAULT_AUTO_DISCOVER,
    DEFAULT_INBOX_DIR,
    DEFAULT_OUTBOX_DIR,
    DEFAULT_WS_URL,
    DOMAIN,
    ERROR_ALIAS_EXISTS,
    ERROR_CANNOT_CONNECT,
    ERROR_INVITE_FAILED,
    ERROR_INVALID_LINK,
    ERROR_TIMEOUT,
    ERROR_WS_NOT_CONNECTED,
)
from .targets import registry_for
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


def _looks_like_simplex_link(link: str) -> bool:
    """Return True when the string can be a SimpleX invitation/address.

    Deliberately tolerant: SimpleX links come in many shapes (``smp://…``,
    ``smp:…``, ``https://simplex.chat/i/#/…``, ``https://smp.simplex.im/#/…``,
    ``https://simplex.chat/g/#/…``) and relays can be self-hosted on a custom
    domain. Only strings that clearly cannot be a link are rejected, so a
    valid but unusual link is never refused — the CLI remains the real
    authority on the link.
    """
    candidate = (link or "").strip()
    if not candidate:
        return False
    lowered = candidate.lower()
    if lowered.startswith(("smp://", "smp:")):
        return True
    parsed = urlparse(candidate)
    host = (parsed.hostname or "").lower()
    if "simplex" in host:
        return True
    if parsed.scheme in ("http", "https"):
        return True
    return False


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
            menu_options=[
                "add_contact",
                "remove_contact",
                "rename_contact",
                "show_targets",
                "install_dashboard",
                "settings",
            ],
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit integration-wide settings (outbox/inbox directories, file auto-accept)."""
        if user_input is not None:
            new_options = {
                **self.config_entry.options,
                CONF_OUTBOX_DIR: user_input[CONF_OUTBOX_DIR].strip() or DEFAULT_OUTBOX_DIR,
                CONF_INBOX_DIR: user_input[CONF_INBOX_DIR].strip() or DEFAULT_INBOX_DIR,
                CONF_AUTO_ACCEPT_FILES: user_input[CONF_AUTO_ACCEPT_FILES],
                CONF_AUTO_DISCOVER: user_input[CONF_AUTO_DISCOVER],
            }
            return self.async_create_entry(title="", data=new_options)

        current_outbox = self.config_entry.options.get(CONF_OUTBOX_DIR, DEFAULT_OUTBOX_DIR)
        current_inbox = self.config_entry.options.get(CONF_INBOX_DIR, DEFAULT_INBOX_DIR)
        current_auto_accept = self.config_entry.options.get(
            CONF_AUTO_ACCEPT_FILES, DEFAULT_AUTO_ACCEPT_FILES
        )
        current_auto_discover = self.config_entry.options.get(
            CONF_AUTO_DISCOVER, DEFAULT_AUTO_DISCOVER
        )
        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_OUTBOX_DIR, default=current_outbox): str,
                    vol.Required(CONF_INBOX_DIR, default=current_inbox): str,
                    vol.Required(CONF_AUTO_ACCEPT_FILES, default=current_auto_accept): bool,
                    vol.Required(CONF_AUTO_DISCOVER, default=current_auto_discover): bool,
                }
            ),
            description_placeholders={
                "hint": (
                    "Outbox : dossier où la tablette dépose les clips avant envoi "
                    "(volume partagé avec simplex-bridge). Inbox : dossier (lecture "
                    "seule) où le CLI écrit les fichiers REÇUS — nécessite un flag "
                    "--files-folder côté bridge pointant vers ce même volume, voir "
                    "DOCKER.md. Sans ça, les pièces jointes reçues s'affichent par "
                    "leur nom mais ne sont pas lisibles dans la carte. "
                    "Auto-découverte : ajoute automatiquement tous les contacts et "
                    "groupes du CLI (plus besoin de coller un lien d'invitation par "
                    "contact)."
                )
            },
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
                    title="", data={**self.config_entry.options, CONF_TARGETS: current}
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
        """Show the configured chats and the auto-discovered ones."""
        current = self.config_entry.options.get(CONF_TARGETS, {})
        lines = [
            f"• **{data.get('name', alias)}** → `{data.get('chat_ref', '?')}`"
            for alias, data in current.items()
        ]

        registry = registry_for(self.hass, self.config_entry.entry_id)
        if registry is not None:
            discovered = registry.discovered
            if discovered:
                lines.append("")
                lines.append("**Découverts automatiquement :**")
                lines.extend(
                    f"• {target.name} → `{target.chat_ref}` (alias `{target.alias}`)"
                    for target in discovered
                )
                lines.append("")
                lines.append(
                    "Les alias derivation ci-dessus peuvent être modifiés via "
                    "« Renommer un contact »."
                )

        if not lines:
            lines = ["*(aucun contact configuré)*"]

        return self.async_show_form(
            step_id="show_targets",
            data_schema=vol.Schema({}),
            description_placeholders={"targets": "\n".join(lines)},
        )

    async def async_step_install_dashboard(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Install one of the bundled Lovelace dashboards."""
        names = available_dashboards()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                result = await async_install_dashboard(
                    self.hass,
                    user_input["dashboard"],
                    user_input.get("url_path") or None,
                    user_input.get("overwrite", False),
                )
            except DashboardInstallError as err:
                errors["base"] = "dashboard_failed"
                _LOGGER.warning("Dashboard install failed: %s", err)
                placeholders = {"error": str(err)}
            else:
                return self.async_abort(
                    reason="dashboard_installed",
                    description_placeholders={
                        "url_path": result["url_path"],
                    },
                )
        else:
            placeholders = {"error": ""}
        return self.async_show_form(
            step_id="install_dashboard",
            data_schema=vol.Schema(
                {
                    vol.Required("dashboard", default=names[0] if names else ""): vol.In(names),
                    vol.Optional("url_path", default=""): str,
                    vol.Optional("overwrite", default=False): bool,
                }
            ),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_rename_contact(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Give a discovered contact/group a custom alias (persisted)."""
        registry = registry_for(self.hass, self.config_entry.entry_id)
        if registry is None:
            return self.async_abort(reason="not_loaded")

        options = {
            target.alias: f"{target.name} ({target.chat_ref})"
            for target in registry.targets
        }
        if not options:
            return self.async_abort(reason="no_targets")

        errors: dict[str, str] = {}
        if user_input is not None:
            alias = user_input["alias"].strip()
            new_alias = user_input.get("new_alias", "").strip()
            target = registry.get(alias)
            if target is None:
                errors["alias"] = "unknown"
            elif not new_alias:
                errors["new_alias"] = "required"
            else:
                current = dict(self.config_entry.options.get(CONF_TARGETS, {}))
                if new_alias in current and new_alias != alias:
                    errors["new_alias"] = ERROR_ALIAS_EXISTS
                else:
                    current.pop(alias, None)
                    current[new_alias] = {
                        "chat_ref": target.chat_ref,
                        "name": target.name,
                        "type": target.type,
                    }
                    return self.async_create_entry(
                        title="", data={**self.config_entry.options, CONF_TARGETS: current}
                    )

        return self.async_show_form(
            step_id="rename_contact",
            data_schema=vol.Schema(
                {
                    vol.Required("alias", default=next(iter(options))): vol.In(options),
                    vol.Required("new_alias"): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "hint": (
                    "Le nouvel alias devient la cible des services "
                    "simplex.send_message / simplex.send_file et le nom des "
                    "entités notify.* correspondantes."
                )
            },
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
                title="", data={**self.config_entry.options, CONF_TARGETS: current}
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