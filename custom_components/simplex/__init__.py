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
    CONF_AUTO_ACCEPT_FILES,
    CONF_INBOX_DIR,
    CONF_OUTBOX_DIR,
    CONF_TARGETS,
    CONF_WS_URL,
    DEFAULT_AUTO_ACCEPT_FILES,
    DEFAULT_INBOX_DIR,
    DEFAULT_OUTBOX_DIR,
    DEFAULT_WS_URL,
    DOMAIN,
    EVENT_MESSAGE_RECEIVED,
    MEDIA_URL_PATH,
    PLATFORMS,
    SERVICE_ACCEPT_INVITE,
    SERVICE_CREATE_INVITE,
    SERVICE_LIST_CONTACTS,
    SERVICE_SEND_FILE,
    SERVICE_SEND_MESSAGE,
)
from .http import SimplexMediaView, SimplexUploadView
from .llm_api import register_llm_api
from .websocket_client import SimplexWsClient, SimplexWsError
from . import ws_api

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# Set once the HTTP upload view / websocket_api commands have been
# registered for this HA instance, so a second config entry (or a reload)
# never tries to register either twice.
_DATA_HTTP_VIEW_REGISTERED = "http_view_registered"
_DATA_WS_API_REGISTERED = "ws_api_registered"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the SimpleX Chat component (services + HTTP view, entry-independent)."""
    hass.data.setdefault(DOMAIN, {})
    if not hass.data[DOMAIN].get(_DATA_HTTP_VIEW_REGISTERED):
        hass.http.register_view(SimplexUploadView(hass))
        hass.http.register_view(SimplexMediaView(hass))
        hass.data[DOMAIN][_DATA_HTTP_VIEW_REGISTERED] = True
    if not hass.data[DOMAIN].get(_DATA_WS_API_REGISTERED):
        ws_api.async_register(hass)
        hass.data[DOMAIN][_DATA_WS_API_REGISTERED] = True
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SimpleX Chat from a config entry."""
    ws_url: str = entry.data.get(CONF_WS_URL, DEFAULT_WS_URL)
    targets: dict[str, Any] = dict(entry.options.get(CONF_TARGETS, {}))
    outbox_dir: str = entry.options.get(CONF_OUTBOX_DIR, DEFAULT_OUTBOX_DIR)
    inbox_dir: str = entry.options.get(CONF_INBOX_DIR, DEFAULT_INBOX_DIR)
    auto_accept_files: bool = entry.options.get(CONF_AUTO_ACCEPT_FILES, DEFAULT_AUTO_ACCEPT_FILES)

    _LOGGER.info(
        "Setting up SimpleX entry %s (ws=%s, %d target(s), outbox=%s, inbox=%s)",
        entry.entry_id,
        ws_url,
        len(targets),
        outbox_dir,
        inbox_dir,
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

    # Ensure the profile is marked as a bot (peerType=bot) so command menus
    # and bot UI behaviour work correctly with SimpleX Chat v7.1.x.
    try:
        await client.ensure_bot_profile(display_name="Home Assistant")
    except Exception as exc:  # noqa: BLE001
        _LOGGER.warning("Could not ensure bot profile: %s", exc)

    # Store runtime data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "targets": targets,
        "entry": entry,
        "outbox_dir": outbox_dir,
        "inbox_dir": inbox_dir,
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
                    _fire_message_event(hass, entry.entry_id, item, targets, inbox_dir)
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("Failed to process incoming chat item")
                if auto_accept_files:
                    file_id = _pending_incoming_file_id(item)
                    if file_id is not None:
                        hass.async_create_task(_accept_file(client, file_id))

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


def _pending_incoming_file_id(item: dict[str, Any]) -> int | None:
    """Return the fileId of an incoming file that hasn't been accepted yet.

    Best-effort: the exact `fileStatus.type` strings for "not yet accepted"
    are not confirmed against every CLI version (see websocket_client.
    receive_file docstring), so we accept on any status that isn't already
    one of the clearly-terminal ones. Worst case this calls receive_file on
    an already-accepted file, which the CLI just no-ops / errors on
    harmlessly (logged at debug level, not raised to the user).
    """
    content = item.get("content") or {}
    file_status = item.get("file") or content.get("file")
    if not isinstance(file_status, dict):
        return None
    status_type = (file_status.get("fileStatus") or {}).get("type") if isinstance(
        file_status.get("fileStatus"), dict
    ) else file_status.get("fileStatus")
    if status_type in ("rcvComplete", "rcvCancelled", "sndComplete", "invalid"):
        return None
    return file_status.get("fileId")


async def _accept_file(client: SimplexWsClient, file_id: int) -> None:
    try:
        await client.receive_file(file_id)
    except SimplexWsError as err:
        _LOGGER.debug("Auto-accept of incoming file %s failed/skipped: %s", file_id, err)


def _resolve_media_url(file_info: dict[str, Any] | None, inbox_dir: str) -> str | None:
    """Return a /api/simplex/media/<name> URL if the file is already on disk.

    Returns None (no playable media yet) until the shared inbox volume
    actually contains it — e.g. right after `receive_file()` was requested
    but before the transfer completed.
    """
    if not file_info or not file_info.get("name"):
        return None
    path = Path(inbox_dir) / file_info["name"]
    if not path.is_file():
        return None
    from urllib.parse import quote

    return f"{MEDIA_URL_PATH}/{quote(file_info['name'])}"


def normalize_chat_item(
    item: dict[str, Any], targets: dict[str, Any], inbox_dir: str | None = None
) -> dict[str, Any] | None:
    """Turn one raw SimpleX chat item into a flat dict the frontend card understands.

    Shared by the live event handler (`_fire_message_event`, below) and the
    `simplex/history` websocket command (`ws_api.py`), so the "same message"
    always looks the same whether it arrived live or was fetched from
    `/chats` — the chat-card bubbles don't have to special-case either path.

    Returns None for item kinds we don't render as a bubble (reactions,
    deletions, system markers, …).
    """
    content = item.get("content") or {}
    msg_content = content.get("msgContent") or {}
    msg_type = content.get("type") or msg_content.get("type")
    if msg_type not in ("text", "sndMsgContent", "rcvMsgContent", "file", "image", "voice"):
        return None

    text = content.get("text") or msg_content.get("text") or ""

    # File / voice / image attachments: surface what we can even without
    # being able to stream the bytes (see DOCKER.md "received files" note).
    file_info = None
    file_status = item.get("file") or content.get("file")
    if isinstance(file_status, dict) or msg_type in ("file", "image", "voice"):
        file_status = file_status if isinstance(file_status, dict) else {}
        file_info = {
            "file_id": file_status.get("fileId"),
            "name": file_status.get("fileName") or msg_content.get("fileName"),
            "size": file_status.get("fileSize"),
            "kind": "image" if msg_type == "image" else "voice" if msg_type == "voice" else "file",
        }
        if inbox_dir:
            file_info["media_url"] = _resolve_media_url(file_info, inbox_dir)

    if not text and not file_info:
        return None

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

    # Best-effort read/delivered status for outgoing bubbles (✓ / ✓✓ in the
    # card). The exact `itemStatus.type` strings (sndNew/sndSent/sndRcvd/
    # sndRead…) are not confirmed against every CLI version, so unknown
    # shapes just fall back to "sent" rather than guessing wrong.
    status = "sent"
    if direction == "outgoing":
        item_status = meta.get("itemStatus") or {}
        status_type = item_status.get("type") if isinstance(item_status, dict) else item_status
        if status_type in ("sndRead",):
            status = "read"
        elif status_type in ("sndRcvd",):
            status = "delivered"

    return {
        "alias": alias,
        "chat_ref": chat_ref,
        "text": text,
        "file": file_info,
        "direction": direction,
        "status": status,
        "item_id": meta.get("itemId"),
        "timestamp": meta.get("itemTs") or meta.get("createdAt"),
        "edited": bool(meta.get("itemEdited")),
    }


def _fire_message_event(
    hass: HomeAssistant,
    entry_id: str,
    item: dict[str, Any],
    targets: dict[str, Any],
    inbox_dir: str | None = None,
) -> None:
    """Translate a SimpleX chat item into a Home Assistant event."""
    normalized = normalize_chat_item(item, targets, inbox_dir)
    if normalized is None:
        return

    hass.bus.async_fire(
        EVENT_MESSAGE_RECEIVED,
        {
            "entry_id": entry_id,
            **normalized,
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

        # Make the link visible from dashboards (Mushroom / buttons don't show
        # service responses). Persistent notification + event.
        await hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": "SimpleX – Invitation",
                "message": (
                    "Lien d'invitation one-time :\n\n"
                    f"`{link}`\n\n"
                    "Copie ce lien (ou scanne-le depuis l'app SimpleX) puis "
                    "partage-le au contact. Il n'est utilisable qu'une seule fois."
                ),
                "notification_id": "simplex_invite_link",
            },
            blocking=False,
        )
        hass.bus.async_fire(
            "simplex_invite_created",
            {"invite_link": link, "entry_id": entry_id},
        )
        # Also store on the entry runtime data for sensors / scripts
        data["last_invite_link"] = link

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
