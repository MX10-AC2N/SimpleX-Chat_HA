"""Home Assistant WebSocket API commands used by the simplex-chat-card frontend.

Why a HA websocket_api command rather than a REST endpoint: the card already
needs to subscribe to HA's event bus for live updates (`simplex_message_
received`), which only works over the same `hass.connection` the frontend
already holds. Piggy-backing the history fetch on that same connection
avoids a second auth/transport path and matches how other HA frontend
cards (e.g. the logbook, history graphs) fetch their initial data.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .websocket_client import SimplexWsClient, SimplexWsError

_LOGGER = logging.getLogger(__name__)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "simplex/history",
        vol.Required("alias"): str,
        vol.Optional("limit", default=50): vol.All(int, vol.Range(min=1, max=200)),
        # Pass the `item_id` of the oldest message currently loaded by the
        # card to page further into the past ("load older" / infinite
        # scroll) — see SimplexWsClient.get_chat_history for the confirmed
        # `/_get chat ... before=<id> count=<limit>` command this maps to.
        vol.Optional("before_item_id"): vol.All(int, vol.Range(min=1)),
        vol.Optional("entry_id"): str,
    }
)
@websocket_api.async_response
async def ws_get_history(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return chat items for one alias, normalized for the chat card.

    Without `before_item_id`: the most recent `limit` messages (initial
    load). With it: up to `limit` messages older than that item — the
    "load older" page. `has_more` tells the card whether another older
    page likely exists (heuristic: a full page came back; the CLI doesn't
    return an authoritative "more remain" flag for this specific query).
    """
    alias = msg["alias"]
    try:
        data = _find_entry_data_for_alias(hass, alias, msg.get("entry_id"))
    except HomeAssistantError as err:
        connection.send_error(msg["id"], "unknown_alias", str(err))
        return

    chat_ref = data["targets"][alias].get("chat_ref")
    if not chat_ref:
        connection.send_error(msg["id"], "unknown_alias", f"Alias '{alias}' has no chat_ref")
        return

    client: SimplexWsClient = data["client"]
    limit = msg["limit"]
    try:
        raw_items = await client.get_chat_history(
            chat_ref, limit=limit, before_item_id=msg.get("before_item_id")
        )
    except SimplexWsError as err:
        connection.send_error(msg["id"], "simplex_error", str(err))
        return

    # Imported here (not at module load) to avoid a circular import with
    # __init__.py, which also uses this normalizer for live events.
    from . import normalize_chat_item

    messages = []
    for raw in raw_items:
        normalized = normalize_chat_item(raw, data.get("targets", {}), data.get("inbox_dir"))
        if normalized is not None:
            messages.append(normalized)

    connection.send_result(
        msg["id"],
        {
            "alias": alias,
            "chat_ref": chat_ref,
            "messages": messages,
            "has_more": len(raw_items) >= limit,
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "simplex/conversations",
        vol.Optional("entry_id"): str,
    }
)
@websocket_api.async_response
async def ws_get_conversations(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return one preview row per known chat (last message + unread count).

    Backs the "home screen" conversation-list card
    (`simplex-conversations-card`). Every chat the integration knows about
    is listed — the manually configured ones *and* the auto-discovered
    contacts/groups — so the card is useful without any manual setup.

    `unread_count` reads `chatStats.unreadCount`, confirmed present on
    every chat preview by reading the CLI's own source (`data ChatStats =
    ChatStats { unreadCount :: Int, ... }` in src/Simplex/Chat/Messages.hs,
    v7.1.4 — the exact version pinned in mx10-ac2n/simplex-bridge) — not a
    guess. The `.get()`/`in` checks below are kept anyway as plain
    defensive coding, not because the field's presence is in doubt.
    """
    from . import normalize_chat_item

    entries = _all_entries(hass, msg.get("entry_id"))
    if not entries:
        connection.send_error(msg["id"], "unknown_alias", "No configured SimpleX entry")
        return

    conversations: list[dict[str, Any]] = []
    for data in entries:
        client: SimplexWsClient = data["client"]
        targets = data.get("targets", {})
        registry = data.get("registry")
        try:
            chats = await client.get_chats()
        except SimplexWsError as err:
            connection.send_error(msg["id"], "simplex_error", str(err))
            return

        by_ref = {}
        for chat in chats:
            info = chat.get("chatInfo") or {}
            contact = info.get("contact") or {}
            group = info.get("groupInfo") or {}
            ref = None
            if contact.get("contactId") is not None:
                ref = f"@{contact['contactId']}"
            elif group.get("groupId") is not None:
                ref = f"#{group['groupId']}"
            if ref:
                by_ref[ref] = chat

        # Every known chat gets a row, even when the CLI has no preview for
        # it yet (a contact that never wrote to us, for instance).
        rows: dict[str, dict[str, Any]] = {}
        for alias, target in targets.items():
            chat_ref = target.get("chat_ref")
            if not chat_ref:
                continue
            rows[chat_ref] = {
                "alias": alias,
                "chat_ref": chat_ref,
                "name": target.get("name") or alias,
                "type": target.get("type", "contact"),
                "discovered": bool(target.get("discovered")),
                "connected": True,
                "last_message": None,
                "unread_count": None,
            }

        for ref, chat in by_ref.items():
            row = rows.get(ref)
            if row is None:
                # A chat the CLI knows about but the registry does not (yet):
                # surface it anyway rather than hiding the conversation.
                info = chat.get("chatInfo") or {}
                contact = info.get("contact") or {}
                group = info.get("groupInfo") or {}
                name = (
                    contact.get("localDisplayName")
                    or group.get("localDisplayName")
                    or ref
                )
                row = {
                    "alias": name,
                    "chat_ref": ref,
                    "name": name,
                    "type": "group" if group else "contact",
                    "discovered": True,
                    "connected": True,
                    "last_message": None,
                    "unread_count": None,
                }
                rows[ref] = row

            items = chat.get("chatItems") or []
            for raw in reversed(items):
                normalized = normalize_chat_item(raw, targets, data.get("inbox_dir"))
                if normalized is not None:
                    row["last_message"] = normalized
                    break
            stats = chat.get("chatStats") or {}
            if isinstance(stats, dict) and "unreadCount" in stats:
                row["unread_count"] = stats.get("unreadCount")
                # Keep the registry in sync so the per-contact unread
                # sensors show the CLI's authoritative counter.
                if registry is not None:
                    registry.update_state(ref, unread_count=stats.get("unreadCount"))

        # Prefer the registry's live state (last message received while HA
        # was running) over the CLI preview when the preview is empty.
        for ref, row in rows.items():
            target = registry.by_ref(ref) if registry is not None else None
            if target is None:
                continue
            row["connected"] = bool(target.connected)
            if row["last_message"] is None and target.last_message:
                row["last_message"] = {
                    "text": target.last_message,
                    "direction": target.last_direction,
                    "timestamp": target.last_timestamp,
                    "alias": target.alias,
                    "chat_ref": ref,
                }
            if row["unread_count"] is None and target.unread_count:
                row["unread_count"] = target.unread_count

        conversations.extend(rows.values())

    connection.send_result(msg["id"], {"conversations": conversations})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "simplex/contacts",
        vol.Optional("entry_id"): str,
    }
)
@websocket_api.async_response
async def ws_get_contacts(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return the known chats and the raw CLI contact/group lists.

    `targets` is the merged view (configured + auto-discovered) with the
    live state; `contacts` and `groups` are the raw records returned by the
    CLI, for UIs that want more than the display name.
    """
    entries = _all_entries(hass, msg.get("entry_id"))
    if not entries:
        connection.send_error(msg["id"], "unknown_alias", "No configured SimpleX entry")
        return

    result: dict[str, Any] = {"targets": {}, "contacts": [], "groups": []}
    for data in entries:
        client: SimplexWsClient = data["client"]
        registry = data.get("registry")
        if registry is not None:
            for target in registry.targets:
                result["targets"][target.alias] = {
                    "chat_ref": target.chat_ref,
                    "name": target.name,
                    "type": target.type,
                    "discovered": target.discovered,
                    "connected": target.connected,
                    "unread_count": target.unread_count,
                    "last_message": target.last_message,
                    "last_timestamp": target.last_timestamp,
                }
        try:
            result["contacts"] = await client.list_contacts()
        except SimplexWsError as err:
            _LOGGER.debug("simplex/contacts: list_contacts failed: %s", err)
        try:
            result["groups"] = await client.list_groups()
        except SimplexWsError as err:
            _LOGGER.debug("simplex/contacts: list_groups failed: %s", err)

    connection.send_result(msg["id"], result)


def _all_entries(hass: HomeAssistant, entry_id: str | None) -> list[dict[str, Any]]:
    domain_data = {
        k: v for k, v in hass.data.get(DOMAIN, {}).items() if isinstance(v, dict) and "client" in v
    }
    if entry_id:
        data = domain_data.get(entry_id)
        return [data] if data else []
    return list(domain_data.values())


def _find_entry_data_for_alias(
    hass: HomeAssistant, alias: str, entry_id: str | None
) -> dict[str, Any]:
    domain_data = {
        k: v for k, v in hass.data.get(DOMAIN, {}).items() if isinstance(v, dict) and "client" in v
    }
    if entry_id:
        data = domain_data.get(entry_id)
        if data and alias in data.get("targets", {}):
            return data
        raise HomeAssistantError(f"Unknown SimpleX alias: {alias}")
    for data in domain_data.values():
        if alias in data.get("targets", {}):
            return data
    raise HomeAssistantError(f"Unknown SimpleX alias: {alias}")


def async_register(hass: HomeAssistant) -> None:
    """Register this module's websocket commands (idempotent at the caller)."""
    websocket_api.async_register_command(hass, ws_get_history)
    websocket_api.async_register_command(hass, ws_get_conversations)
    websocket_api.async_register_command(hass, ws_get_contacts)
