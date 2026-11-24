"""Normalisation of the raw SimpleX chat items into the flat shape used by
the Home Assistant entities and the Lovelace cards.

This module is deliberately free of any Home Assistant import (except the
constants), so it can be unit-tested against real captured CLI frames
without a running Home Assistant.

Serialisation proven against CLI 7.1.4.0 (ws-validate reference run of
mx10-ac2n/simplex-bridge):

    resp.chatItems[] = {                      <- wrapper
      "chatInfo": {"type": "direct",
                   "contact": {"contactId": 3, "localDisplayName": "AC2N", ...}},
      "chatItem": {"itemId": 17,
                   "meta":  {"chatDir": {"type": "directRcv"},
                             "itemText": "Alors tu reçois", ...},
                   "content": {"type": "text", "text": "Alors tu reçois", ...}}}

Both the v7 wrapper and the legacy flat shapes are supported, so this
keeps working with older CLIs and with whatever shape `/chats` returns.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .const import MEDIA_URL_PATH
from .targets import sanitize_alias

# Items protocolaires générés automatiquement par le CLI v7 à l'établissement
# d'une connexion (chatBanner, infos E2EE, annonces de features). Cartographiés
# en direct par la suite ws-validate (CLI 7.1.4.0) : ils portent un itemText
# non vide ("chat banner"), il faut donc les filtrer PAR TYPE et non par
# absence de texte, sinon chaque connexion génère des bulles/event fantômes.
SYSTEM_CONTENT_TYPES = frozenset(
    {
        "chatBanner",
        "rcvDirectE2EEInfo",
        "sndDirectE2EEInfo",
        "rcvChatFeature",
        "sndChatFeature",
        "intro",
        "autoReply",
    }
)

# Types de contenu rendus comme une bulle dans la carte.
RENDERABLE_CONTENT_TYPES = (
    "text",
    "sndMsgContent",
    "rcvMsgContent",
    "file",
    "image",
    "voice",
    "video",
)


def unwrap_chat_item(item: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (chat_info, chat_item) for both known serialisations.

    CLI v6+/v7 (live events /_subscribe, /chats) wrap each item:
        {"chatInfo": {...}, "chatItem": {"itemId", "meta", "content", ...}}
    Legacy / flat forms (older CLIs, some RPC replies) hand the chatItem
    directly. Reading `meta` off the wrapper silently yields an empty dict —
    which is exactly the bug that made item_id/timestamp/edited always empty.
    """
    if not isinstance(item, dict):
        return {}, {}
    chat_info = item.get("chatInfo") or {}
    chat_item = item.get("chatItem")
    if isinstance(chat_item, dict):
        return chat_info if isinstance(chat_info, dict) else {}, chat_item
    return chat_info if isinstance(chat_info, dict) else {}, item


def msg_content(chat_item: dict[str, Any]) -> dict[str, Any]:
    """Return the discriminated message content, whichever serialisation:
    - v7 short form  : chatItem.content.{type,text,...}
    - documented form: chatItem.content.msgContent.{type,text,fileName,...}
    - flat form      : chatItem.msgContent
    """
    content = chat_item.get("content")
    if isinstance(content, dict):
        mc = content.get("msgContent")
        if isinstance(mc, dict):
            return mc
        if "type" in content:
            return content
    mc = chat_item.get("msgContent")
    return mc if isinstance(mc, dict) else {}


def pending_incoming_file_id(item: dict[str, Any]) -> int | None:
    """Return the fileId of an incoming file that hasn't been accepted yet.

    Best-effort: the exact `fileStatus.type` strings for "not yet accepted"
    are not confirmed against every CLI version (see websocket_client.
    receive_file docstring), so we accept on any status that isn't already
    one of the clearly-terminal ones. Worst case this calls receive_file on
    an already-accepted file, which the CLI just no-ops / errors on
    harmlessly (logged at debug level, not raised to the user).

    Handles the v7 wrapper (file metadata lives in chatItem.meta.itemFile)
    as well as the legacy placements.
    """
    _, chat_item = unwrap_chat_item(item)
    meta = chat_item.get("meta") or {}
    content = chat_item.get("content") or {}
    file_status = meta.get("itemFile") or chat_item.get("file") or content.get("file")
    if not isinstance(file_status, dict):
        return None
    status_type = (file_status.get("fileStatus") or {}).get("type") if isinstance(
        file_status.get("fileStatus"), dict
    ) else file_status.get("fileStatus")
    if status_type in ("rcvComplete", "rcvCancelled", "sndComplete", "invalid"):
        return None
    return file_status.get("fileId")


def resolve_media_url(file_info: dict[str, Any] | None, inbox_dir: str) -> str | None:
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

    Shared by the live event handler (`_fire_message_event`) and the
    `simplex/history` websocket command (`ws_api.py`), so the "same message"
    always looks the same whether it arrived live or was fetched from
    `/chats` — the chat-card bubbles don't have to special-case either path.

    Returns None for item kinds we don't render as a bubble (reactions,
    deletions, system markers, …).
    """
    chat_info, chat_item = unwrap_chat_item(item)
    if not chat_item:
        return None

    meta = chat_item.get("meta") if isinstance(chat_item.get("meta"), dict) else {}
    content_dict = msg_content(chat_item)
    msg_type = content_dict.get("type")

    # System/protocol items (chat banner, E2EE info, chat-feature notices):
    # filtered by type, before anything else — they carry a non-empty
    # itemText ("chat banner"), so a "not text and not file" test would NOT
    # catch them.
    if msg_type in SYSTEM_CONTENT_TYPES:
        return None

    if msg_type not in RENDERABLE_CONTENT_TYPES:
        return None

    # Display text: meta.itemText is the reliable CLI v7 field (present on
    # text messages and on file/image captions alike); fall back to the
    # older msgContent placements.
    text = (
        meta.get("itemText")
        or content_dict.get("text")
        or content_dict.get("fileName")
        or ""
    )

    # File / voice / image / video attachments: surface what we can even
    # without being able to stream the bytes (see DOCKER.md "received files"
    # note). CLI v7 exposes the transfer metadata in meta.itemFile.
    file_info = None
    file_status = (
        meta.get("itemFile") or chat_item.get("file") or content_dict.get("file")
    )
    if isinstance(file_status, dict) or msg_type in ("file", "image", "voice", "video"):
        file_status = file_status if isinstance(file_status, dict) else {}
        file_info = {
            "file_id": file_status.get("fileId"),
            "name": file_status.get("fileName") or content_dict.get("fileName"),
            "size": file_status.get("fileSize"),
            "kind": (
                "image"
                if msg_type == "image"
                else "voice"
                if msg_type == "voice"
                else "file"  # video maps to "file" so the card needs no change
            ),
        }
        if inbox_dir:
            file_info["media_url"] = resolve_media_url(file_info, inbox_dir)

    if not text and not file_info:
        return None

    contact = chat_info.get("contact") or {}
    group = chat_info.get("groupInfo") or {}
    chat_ref = None
    alias = None
    display_name = None
    chat_type = "contact"

    if contact:
        cid = contact.get("contactId")
        if cid is not None:
            chat_ref = f"@{cid}"
            display_name = (
                contact.get("localDisplayName")
                or (contact.get("profile") or {}).get("displayName")
            )
    elif group:
        gid = group.get("groupId")
        if gid is not None:
            chat_ref = f"#{gid}"
            chat_type = "group"
            display_name = (
                group.get("localDisplayName")
                or (group.get("groupProfile") or {}).get("displayName")
            )

    if chat_ref:
        for a, data in targets.items():
            if data.get("chat_ref") == chat_ref:
                alias = a
                break
        if alias is None and display_name:
            # The chat is neither configured nor auto-discovered. Fall back
            # to a sanitised display name so the message still reaches a
            # named recipient instead of being an orphan.
            alias = sanitize_alias(display_name, fallback=chat_ref)

    # Direction: the CLI v7 puts it in meta.chatDir.type ("directRcv" /
    # "directSnd", "groupRcv" / "groupSnd"). The documented ChatItem type
    # places chatDir one level up, and older CLIs used meta.direction — all
    # three are accepted. Everything ending in "snd" is outgoing, so group
    # chats are covered too. Unreadable shapes fall back to "incoming"
    # (same as the old behaviour) rather than guessing wrong.
    chat_dir = meta.get("chatDir") if isinstance(meta.get("chatDir"), dict) else None
    if chat_dir is not None:
        dir_type = chat_dir.get("type")
    elif isinstance(chat_item.get("chatDir"), dict):
        # Documented ChatItem shape places chatDir one level above meta.
        dir_type = chat_item["chatDir"].get("type")
    else:
        direction_meta = meta.get("direction")
        dir_type = (
            direction_meta.get("type")
            if isinstance(direction_meta, dict)
            else direction_meta
        )
    direction = "outgoing" if str(dir_type or "").lower().endswith("snd") else "incoming"

    # Best-effort read/delivered status for outgoing bubbles (✓ / ✓✓ in the
    # card). The CLI v7 CIStatus enum is sndNew | sndSent | sndRcvd |
    # sndError | sndWarning | rcvNew | rcvRead | invalid — so "sndRcvd"
    # means "delivered", and "sndRead" is kept as a tolerant extra for
    # older builds that did emit it.
    status = "sent"
    if direction == "outgoing":
        item_status = meta.get("itemStatus") or {}
        status_type = (
            item_status.get("type") if isinstance(item_status, dict) else item_status
        )
        if status_type in ("sndRead",):
            status = "read"
        elif status_type in ("sndRcvd",):
            status = "delivered"
        elif status_type in ("sndNew",):
            status = "sending"

    return {
        "alias": alias,
        "chat_ref": chat_ref,
        "display_name": display_name,
        "type": chat_type,
        "text": text,
        "file": file_info,
        "direction": direction,
        "status": status,
        # CLI v7 puts the item id at the chatItem level (confirmed on the
        # real captured frames: `chatItem.itemId`); the documented CIMeta
        # type puts it in `meta.itemId` — both are accepted.
        "item_id": chat_item.get("itemId") or meta.get("itemId"),
        "timestamp": meta.get("itemTs") or meta.get("createdAt"),
        "edited": bool(meta.get("itemEdited")),
    }
