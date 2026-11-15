"""The SimpleX Chat integration for Home Assistant."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
import voluptuous as vol

from .const import (
    CONF_OUTBOX_DIR,
    CONF_TARGETS,
    CONF_WS_URL,
    DEFAULT_OUTBOX_DIR,
    DEFAULT_WS_URL,
    DOMAIN,
    EVENT_MESSAGE_RECEIVED,
    PLATFORMS,
    SERVICE_ACCEPT_INVITE,
    SERVICE_CREATE_INVITE,
    SERVICE_LIST_CONTACTS,
    SERVICE_SEND_FILE,
    SERVICE_SEND_MESSAGE,
)
from .http import SimplexUploadView
from .llm_api import register_llm_api
from .websocket_client import SimplexWsClient, SimplexWsError

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# Set once the HTTP upload view has been registered for this HA instance,
# so a second config entry (or a reload) never tries to register it twice.
_DATA_HTTP_VIEW_REGISTERED = "http_view_registered"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the SimpleX Chat component (services + HTTP view, entry-independent)."""
    hass.data.setdefault(DOMAIN, {})
    if not hass.data[DOMAIN].get(_DATA_HTTP_VIEW_REGISTERED):
        hass.http.register_view(SimplexUploadView(hass))
        hass.data[DOMAIN][_DATA_HTTP_VIEW_REGISTERED] = True
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SimpleX Chat from a config entry."""
    ws_url: str = entry.data.get(CONF_WS_URL, DEFAULT_WS_URL)
    targets: dict[str, Any] = dict(entry.options.get(CONF_TARGETS, {}))
    outbox_dir: str = entry.options.get(CONF_OUTBOX_DIR, DEFAULT_OUTBOX_DIR)

    _LOGGER.info(
        "Setting up SimpleX entry %s (ws=%s, %d target(s), outbox=%s)",
        entry.entry_id,
        ws_url,
        len(targets),
        outbox_dir,
    )

    # The outbox directory must exist so the HTTP upload view can write into
    # it immediately; it must also be shared (bind-mounted) with the
    # container running the simplex-chat CLI, otherwise `/f` will fail with
    # a "file not found" chatCmdError when the CLI tries to read it.
    try:
        await hass.async_add_executor_job(
            lambda: Path(outbox_dir).mkdir(parents=True, exist_ok=True)
        )
    except OSError as exc:
        _LOGGER.warning("Could not create outbox directory %s: %s", outbox_dir, exc)

    client = SimplexWsClient(ws_url, hass.loop)
    try:
        await client.connect()
    except (OSError, aiohttp.ClientError, TimeoutError) as exc:
        await client.close()
        raise ConfigEntryNotReady(
            f"Cannot connect to SimpleX websocket at {ws_url}: {exc}"
        ) from exc

    # Store runtime data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "targets": targets,
        "entry": entry,
        "outbox_dir": outbox_dir,
    }

    # Forward platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register the LLM / Assist tool for this entry. The `llm` helper has no
    # unregister API, so a reload (which tears down and re-runs this
    # function with the *same* entry_id, hence the same stable api id) would
    # otherwise raise "API already registered". We register once and treat
    # a repeat registration as a no-op: the tool reads `targets` from
    # hass.data dynamically on every call, so the already-registered
    # instance stays correct across reloads.
    register_llm_api(hass, entry)

    # Wire incoming message events → HA events
    def _on_ws_event(raw: dict[str, Any]) -> None:
        resp = raw.get("resp") if isinstance(raw, dict) else None
        if not isinstance(resp, dict):
            return
        etype = resp.get("type")
        if etype in ("newChatItems", "chatItemsCreated"):
            items = resp.get("chatItems") or resp.get("chatItem") or []
            if not isinstance(items, list):
                items = [items]
            for item in items:
                try:
                    _fire_message_event(hass, entry.entry_id, item, targets)
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("Failed to process incoming chat item")

    remove_handler = client.add_event_handler(_on_ws_event)
    entry.async_on_unload(remove_handler)

    # Register domain services (idempotent, guarded)
    if not hass.services.has_service(DOMAIN, SERVICE_SEND_MESSAGE):
        _register_services(hass)

    # NOTE: we deliberately do NOT also register an options update listener
    # that calls async_reload() here. The options flow already extends
    # OptionsFlowWithReload, which reloads the entry itself. Combining both
    # causes a double reload / race condition that Home Assistant has
    # deprecated since 2026.6 and turns into a hard error from 2026.12.

    _LOGGER.info("SimpleX entry %s ready", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    data = hass.data[DOMAIN].pop(entry.entry_id, None)
    if data and "client" in data:
        await data["client"].close()
    return unloaded


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _fire_message_event(
    hass: HomeAssistant,
    entry_id: str,
    item: dict[str, Any],
    targets: dict[str, Any],
) -> None:
    """Translate a SimpleX chat item into a Home Assistant event."""
    content = item.get("content") or {}
    msg_type = content.get("type") or content.get("msgContent", {}).get("type")
    if msg_type not in ("text", "sndMsgContent", "rcvMsgContent"):
        return

    text = (
        content.get("text")
        or content.get("msgContent", {}).get("text")
        or ""
    )
    if not text:
        return

    # Try to resolve a friendly alias
    chat_info = item.get("chatInfo") or {}
    contact = chat_info.get("contact") or {}
    group = chat_info.get("groupInfo") or {}
    chat_ref = None
    alias = None

    if contact:
        cid = contact.get("contactId")
        if cid is not None:
            chat_ref = f"@{cid}"
    elif group:
        gid = group.get("groupId")
        if gid is not None:
            chat_ref = f"#{gid}"

    if chat_ref:
        for a, data in targets.items():
            if data.get("chat_ref") == chat_ref:
                alias = a
                break

    meta = item.get("meta") or {}
    direction_meta = meta.get("direction")
    direction = (
        "outgoing"
        if isinstance(direction_meta, dict) and direction_meta.get("type") == "directSnd"
        else "incoming"
    )

    hass.bus.async_fire(
        EVENT_MESSAGE_RECEIVED,
        {
            "entry_id": entry_id,
            "alias": alias,
            "chat_ref": chat_ref,
            "text": text,
            "direction": direction,
            "item_id": meta.get("itemId"),
            "raw": item,
        },
    )


# ------------------------------------------------------------------
# Services
# ------------------------------------------------------------------


def _register_services(hass: HomeAssistant) -> None:
    """Register domain services."""

    async def handle_send_message(call: ServiceCall) -> None:
        alias = call.data["alias"]
        message = call.data["message"]
        title = call.data.get("title")
        data = _get_entry_data_for_alias(hass, alias)
        client: SimplexWsClient = data["client"]
        chat_ref = data["targets"][alias].get("chat_ref")
        if not chat_ref:
            raise HomeAssistantError(f"Alias '{alias}' has no chat_ref")
        full = f"{title}: {message}" if title else message
        try:
            await client.send_text(chat_ref, full)
        except SimplexWsError as err:
            raise HomeAssistantError(str(err)) from err

    async def handle_send_file(call: ServiceCall) -> None:
        alias = call.data["alias"]
        file_path = call.data["file_path"]
        data = _get_entry_data_for_alias(hass, alias)
        client: SimplexWsClient = data["client"]
        chat_ref = data["targets"][alias].get("chat_ref")
        if not chat_ref:
            raise HomeAssistantError(f"Alias '{alias}' has no chat_ref")
        if not await hass.async_add_executor_job(Path(file_path).is_file):
            raise HomeAssistantError(f"File not found: {file_path}")
        try:
            await client.send_file(chat_ref, file_path)
        except SimplexWsError as err:
            raise HomeAssistantError(str(err)) from err

    async def handle_create_invite(call: ServiceCall) -> dict[str, Any]:
        entry_id = call.data.get("entry_id")
        data = _get_entry_data(hass, entry_id)
        client: SimplexWsClient = data["client"]
        try:
            link = await client.create_invite()
        except SimplexWsError as err:
            raise HomeAssistantError(str(err)) from err
        return {"invite_link": link}

    async def handle_list_contacts(call: ServiceCall) -> dict[str, Any]:
        entry_id = call.data.get("entry_id")
        data = _get_entry_data(hass, entry_id)
        client: SimplexWsClient = data["client"]
        try:
            contacts = await client.list_contacts()
        except SimplexWsError as err:
            raise HomeAssistantError(str(err)) from err
        return {"contacts": contacts}

    async def handle_accept_invite(call: ServiceCall) -> dict[str, Any]:
        entry_id = call.data.get("entry_id")
        link = call.data["invite_link"]
        alias = call.data.get("alias")
        data = _get_entry_data(hass, entry_id)
        client: SimplexWsClient = data["client"]
        entry: ConfigEntry = data["entry"]

        try:
            result = await client.accept_invite_link(link)
        except SimplexWsError as err:
            raise HomeAssistantError(str(err)) from err

        chat_ref = result.get("chat_ref")
        if not chat_ref:
            raise HomeAssistantError("Invite accepted but no chat reference returned")

        if alias:
            targets = dict(entry.options.get(CONF_TARGETS, {}))
            if alias in targets:
                raise HomeAssistantError(f"Alias '{alias}' already exists")
            targets[alias] = {
                "chat_ref": chat_ref,
                "name": alias,
                "type": result.get("type", "contact"),
            }
            hass.config_entries.async_update_entry(
                entry, options={**entry.options, CONF_TARGETS: targets}
            )

        return {"chat_ref": chat_ref, "type": result.get("type"), "alias": alias}

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        handle_send_message,
        schema=vol.Schema(
            {
                vol.Required("alias"): cv.string,
                vol.Required("message"): cv.string,
                vol.Optional("title"): cv.string,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_FILE,
        handle_send_file,
        schema=vol.Schema(
            {
                vol.Required("alias"): cv.string,
                vol.Required("file_path"): cv.string,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_INVITE,
        handle_create_invite,
        schema=vol.Schema({vol.Optional("entry_id"): cv.string}),
        supports_response=True,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_LIST_CONTACTS,
        handle_list_contacts,
        schema=vol.Schema({vol.Optional("entry_id"): cv.string}),
        supports_response=True,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_ACCEPT_INVITE,
        handle_accept_invite,
        schema=vol.Schema(
            {
                vol.Required("invite_link"): cv.string,
                vol.Optional("alias"): cv.string,
                vol.Optional("entry_id"): cv.string,
            }
        ),
        supports_response=True,
    )


def _get_entry_data(hass: HomeAssistant, entry_id: str | None) -> dict[str, Any]:
    domain_data = {k: v for k, v in hass.data.get(DOMAIN, {}).items() if isinstance(v, dict) and "client" in v}
    if entry_id and entry_id in domain_data:
        return domain_data[entry_id]
    if len(domain_data) == 1:
        return next(iter(domain_data.values()))
    raise HomeAssistantError(
        "Multiple SimpleX entries exist; please specify entry_id"
    )


def _get_entry_data_for_alias(hass: HomeAssistant, alias: str) -> dict[str, Any]:
    """Find the entry that owns the given alias (searches across all entries)."""
    for entry_id, data in hass.data.get(DOMAIN, {}).items():
        if not isinstance(data, dict) or "client" not in data:
            continue
        if alias in data.get("targets", {}):
            return data
    raise HomeAssistantError(f"Unknown SimpleX alias: {alias}")
