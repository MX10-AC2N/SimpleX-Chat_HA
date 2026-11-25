"""The SimpleX Chat integration for Home Assistant."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
import voluptuous as vol

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
    EVENT_ERROR,
    EVENT_MESSAGE_RECEIVED,
    EVENT_TARGETS_UPDATED,
    PLATFORMS,
    SERVICE_ACCEPT_INVITE,
    SERVICE_CREATE_INVITE,
    SERVICE_LIST_CONTACTS,
    SERVICE_LIST_GROUPS,
    SERVICE_MARK_READ,
    SERVICE_REFRESH_CONTACTS,
    SERVICE_SEND_FILE,
    SERVICE_SEND_MESSAGE,
)
from .http import SimplexMediaView, SimplexUploadView
from .llm_api import register_llm_api
from .mapping import normalize_chat_item, pending_incoming_file_id
from .targets import SimplexTargetRegistry
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
    auto_discover: bool = entry.options.get(CONF_AUTO_DISCOVER, DEFAULT_AUTO_DISCOVER)

    # The device used to be named "SimpleX Chat", which slugifies to
    # `simple_x_chat_*`, while the README and the shipped dashboards have
    # always documented `simplex_chat_*`. Every dashboard card therefore
    # showed "entity not found". The device is now named "Simplex Chat";
    # Home Assistant does not rename entity ids when a device is renamed,
    # so existing installs are migrated here, once.
    _migrate_entity_ids(hass, entry)

    _LOGGER.info(
        "Setting up SimpleX entry %s (ws=%s, %d configured target(s), "
        "outbox=%s, inbox=%s, auto_discover=%s)",
        entry.entry_id,
        ws_url,
        len(targets),
        outbox_dir,
        inbox_dir,
        auto_discover,
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

    # Store runtime data. `targets` holds the *merged* view of the manually
    # configured targets and the auto-discovered ones; it is refreshed every
    # time the registry changes so every consumer (notify entities,
    # sensors, the LLM tool, the websocket API) always sees the same list.
    registry = SimplexTargetRegistry(targets)
    hass.data.setdefault(DOMAIN, {})
    entry_data: dict[str, Any] = {
        "client": client,
        "targets": registry.all(),
        "registry": registry,
        "entry": entry,
        "outbox_dir": outbox_dir,
        "inbox_dir": inbox_dir,
    }
    hass.data[DOMAIN][entry.entry_id] = entry_data

    # ------------------------------------------------------------------
    # Auto-discovery of the CLI's contacts and groups
    # ------------------------------------------------------------------
    # Without this, every chat had to be configured by hand with a one-time
    # invitation link, which made incoming messages from unconfigured
    # contacts invisible ("orphan" messages). It runs *before* the
    # platforms are forwarded so the very first entity set already covers
    # every known chat.
    if auto_discover:
        try:
            await _refresh_targets(hass, entry, client, registry)
        except SimplexWsError as exc:
            _LOGGER.warning("SimpleX auto-discovery failed: %s", exc)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected error during SimpleX auto-discovery")

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

        # Contact / group lifecycle: keep the registry in sync so a contact
        # accepted while HA is running shows up without a restart.
        if etype in CONTACT_EVENT_TYPES:
            _handle_contact_event(hass, entry, registry, resp)
            return

        if etype in ("newChatItems", "chatItemsCreated"):
            items = resp.get("chatItems") or resp.get("chatItem") or []
            if not isinstance(items, list):
                items = [items]
            for item in items:
                try:
                    _fire_message_event(
                        hass,
                        entry.entry_id,
                        item,
                        entry_data["targets"],
                        inbox_dir,
                        registry,
                    )
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("Failed to process incoming chat item")
                if auto_accept_files:
                    file_id = pending_incoming_file_id(item)
                    if file_id is not None:
                        hass.async_create_task(_accept_file(client, file_id))

    remove_handler = client.add_event_handler(_on_ws_event)
    entry.async_on_unload(remove_handler)

    # Contacts accepted (auto-accept) or deleted while the websocket was down
    # produce no event we could see: re-read the CLI's lists after every
    # reconnection so the registry never drifts.
    if auto_discover:

        def _on_connection_change(connected: bool) -> None:
            if connected:
                entry.async_create_background_task(
                    hass,
                    _refresh_targets(hass, entry, client, registry),
                    f"simplex resync {entry.entry_id}",
                )

        entry.async_on_unload(client.add_connection_listener(_on_connection_change))

    # Surface CLI errors (chatCmdError) as HA events so they are visible in
    # the logbook and can drive a dashboard card.
    def _on_ws_error(error: dict[str, Any]) -> None:
        _LOGGER.warning(
            "SimpleX CLI error: %s (reason=%s, cmd=%s)",
            error.get("message"),
            error.get("reason"),
            error.get("command"),
        )
        hass.bus.async_fire(EVENT_ERROR, {"entry_id": entry.entry_id, **error})

    remove_error_handler = client.add_error_listener(_on_ws_error)
    entry.async_on_unload(remove_error_handler)

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

# The entity ids the integration used to generate, because the device was
# named "SimpleX Chat" (slugified: `simple_x_chat`).
_LEGACY_ENTITY_ID_MARKER = "simple_x_chat_"


def legacy_entity_id_to_new(entity_id: str) -> str | None:
    """Return the current id for a legacy entity id, or None if it is current.

    The integration device is named "Simplex Chat", so the entities now
    live at `sensor.simplex_chat_last_message` & co. — the ids the README
    and the shipped dashboards have always used. Installs created before
    that rename still have the `*_simple_x_chat_*` ids.
    """
    if _LEGACY_ENTITY_ID_MARKER not in entity_id:
        return None
    return entity_id.replace(_LEGACY_ENTITY_ID_MARKER, "simplex_chat_")


def _migrate_entity_ids(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Rename the integration's entities to their documented ids.

    Home Assistant derives an entity id from the *device* name, and does
    not regenerate it when the device is renamed. This integration's
    device is now named "Simplex Chat", so the entities live at
    `sensor.simplex_chat_last_message` & co. — the ids the README and the
    shipped dashboards have always used.

    Existing installs registered the entities under the old
    `*_simple_x_chat_*` ids; they are renamed here, once, so the
    dashboards start working without any manual action.
    """
    try:
        from homeassistant.helpers import entity_registry as er
    except ImportError:  # pragma: no cover - Home Assistant always has it
        return

    registry = er.async_get(hass)
    for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        old_id = reg_entry.entity_id
        new_id = legacy_entity_id_to_new(old_id)
        if new_id is None:
            continue
        domain = old_id.split(".", 1)[0]
        if reg_entry.unique_id:
            current_id = registry.async_get_entity_id(
                domain, reg_entry.platform, reg_entry.unique_id
            )
            if current_id and current_id != old_id:
                # Already migrated (or the id has been taken meanwhile):
                # leave the entity alone.
                continue
        try:
            registry.async_update_entity(old_id, new_entity_id=new_id)
        except HomeAssistantError as err:
            _LOGGER.warning(
                "Could not rename entity %s to %s: %s", old_id, new_id, err
            )
        else:
            _LOGGER.info("Renamed entity %s -> %s", old_id, new_id)


async def _accept_file(client: SimplexWsClient, file_id: int) -> None:
    try:
        await client.receive_file(file_id)
    except SimplexWsError as err:
        _LOGGER.debug("Auto-accept of incoming file %s failed/skipped: %s", file_id, err)


def _fire_message_event(
    hass: HomeAssistant,
    entry_id: str,
    item: dict[str, Any],
    targets: dict[str, Any],
    inbox_dir: str | None = None,
    registry: SimplexTargetRegistry | None = None,
) -> dict[str, Any] | None:
    """Translate a SimpleX chat item into a Home Assistant event.

    The per-chat state (last message, unread counter) is updated *before*
    the event is fired, so any listener reading the registry already sees
    the new state. Returns the normalized message, or None when the item is
    not renderable.
    """
    normalized = normalize_chat_item(item, targets, inbox_dir)
    if normalized is None:
        return None

    if registry is not None:
        _apply_message_to_registry(registry, normalized)

    hass.bus.async_fire(
        EVENT_MESSAGE_RECEIVED,
        {
            "entry_id": entry_id,
            **normalized,
            "raw": item,
        },
    )
    return normalized


# ------------------------------------------------------------------
# Auto-discovery of contacts and groups
# ------------------------------------------------------------------

# CLI events that change the set of known chats (official Bot API
# "Contact connection events" + the group ones). Each of them is handled
# so a contact accepted while HA is running appears without a restart.
CONTACT_EVENT_TYPES = frozenset(
    {
        "contactConnected",
        "contactSndReady",
        "contactUpdated",
        "contactDeletedByContact",
        "contactDeleted",
        "receivedContactRequest",
        "newMemberContactReceivedInv",
        "userJoinedGroup",
        "groupUpdated",
        # The user left / was removed from a group, or the group was deleted.
        "leftMemberUser",
        "deletedMemberUser",
        "groupDeleted",
    }
)

# Events after which the chat can no longer be written to.
_CHAT_GONE_EVENTS = frozenset(
    {
        "contactDeletedByContact",
        "contactDeleted",
        "leftMemberUser",
        "deletedMemberUser",
        "groupDeleted",
    }
)

# memberStatus values of *our own* membership meaning "we are out of the group".
_DEAD_GROUP_STATUSES = frozenset({"removed", "left", "deleted", "rejected", "group_deleted"})

# ContactStatus enum of the CLI v7: active | deleted | deletedByUser | rejected
_DEAD_CONTACT_STATUSES = frozenset({"deleted", "deletedByUser", "rejected"})


def _contact_display_name(contact: dict[str, Any], fallback: str) -> str:
    """Return the best human name for a contact."""
    return str(
        contact.get("localDisplayName")
        or (contact.get("profile") or {}).get("displayName")
        or fallback
    )


def _group_display_name(group: dict[str, Any], fallback: str) -> str:
    """Return the best human name for a group."""
    return str(
        group.get("localDisplayName")
        or (group.get("groupProfile") or {}).get("displayName")
        or fallback
    )


async def _refresh_targets(
    hass: HomeAssistant,
    entry: ConfigEntry,
    client: SimplexWsClient,
    registry: SimplexTargetRegistry,
) -> bool:
    """Re-read the CLI's contacts and groups and update the registry.

    Returns True when at least one chat was newly registered.
    """
    contacts: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []
    failures: list[str] = []

    try:
        contacts = await client.list_contacts()
    except SimplexWsError as exc:
        failures.append(f"contacts: {exc}")
    try:
        groups = await client.list_groups()
    except SimplexWsError as exc:
        failures.append(f"groups: {exc}")
    if failures:
        # Not debug-level: a silent failure here looks exactly like "the CLI
        # has no contacts", which is the confusing "nothing shows up" symptom.
        _LOGGER.warning("SimpleX auto-discovery incomplete (%s)", "; ".join(failures))

    created = False

    for contact in contacts:
        if not isinstance(contact, dict):
            continue
        cid = contact.get("contactId")
        if cid is None:
            continue
        status = contact.get("contactStatus")
        if status in _DEAD_CONTACT_STATUSES:
            continue
        _, is_new = registry.upsert_discovered(
            f"@{cid}",
            _contact_display_name(contact, f"Contact {cid}"),
            "contact",
            status in (None, "active"),
        )
        created = created or is_new

    for group in groups:
        # Some CLI builds list groups as [GroupInfo, GroupSummary] pairs.
        if isinstance(group, (list, tuple)) and group:
            group = group[0]
        if not isinstance(group, dict):
            continue
        gid = group.get("groupId")
        if gid is None:
            continue
        member_status = str((group.get("membership") or {}).get("memberStatus") or "")
        if member_status.replace("-", "_").lower() in _DEAD_GROUP_STATUSES:
            continue  # we left / were removed: nothing can be sent there
        _, is_new = registry.upsert_discovered(
            f"#{gid}",
            _group_display_name(group, f"Group {gid}"),
            "group",
            True,
        )
        created = created or is_new

    _LOGGER.info(
        "SimpleX auto-discovery: %d contact(s), %d group(s) known (%d auto-discovered)",
        len(contacts),
        len(groups),
        len(registry.discovered),
    )
    _sync_targets(hass, entry, registry, created)
    return created


def _sync_targets(
    hass: HomeAssistant,
    entry: ConfigEntry,
    registry: SimplexTargetRegistry,
    changed: bool = False,
) -> None:
    """Refresh the merged targets view and notify the entity platforms."""
    data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if isinstance(data, dict):
        data["targets"] = registry.all()
    if changed:
        hass.bus.async_fire(
            EVENT_TARGETS_UPDATED,
            {
                "entry_id": entry.entry_id,
                "aliases": [target.alias for target in registry.targets],
            },
        )


def _handle_contact_event(
    hass: HomeAssistant,
    entry: ConfigEntry,
    registry: SimplexTargetRegistry,
    resp: dict[str, Any],
) -> None:
    """Handle a contact / group lifecycle event coming from the CLI."""
    etype = resp.get("type")
    created = False

    contact = resp.get("contact") or resp.get("fromContact") or {}
    if not isinstance(contact, dict):
        contact = {}
    group = resp.get("groupInfo") or resp.get("group") or {}
    if not isinstance(group, dict):
        group = {}

    cid = contact.get("contactId")
    gid = group.get("groupId")

    if cid is not None:
        connected = etype not in _CHAT_GONE_EVENTS
        _, is_new = registry.upsert_discovered(
            f"@{cid}",
            _contact_display_name(contact, f"Contact {cid}"),
            "contact",
            connected,
        )
        created = created or is_new
        _LOGGER.info(
            "SimpleX event %s → contact @%s (%s)",
            etype,
            cid,
            "connected" if connected else "deleted",
        )
    elif gid is not None:
        _, is_new = registry.upsert_discovered(
            f"#{gid}",
            _group_display_name(group, f"Group {gid}"),
            "group",
            etype not in _CHAT_GONE_EVENTS,
        )
        created = created or is_new
    elif etype == "receivedContactRequest":
        request = resp.get("contactRequest") or {}
        name = request.get("localDisplayName") if isinstance(request, dict) else None
        _LOGGER.info(
            "SimpleX received a contact request from %s — accept it in SimpleX "
            "Chat, or enable auto-accept in the bridge (SIMPLEX_AUTO_ACCEPT=true).",
            name or "an unknown contact",
        )

    _sync_targets(hass, entry, registry, created)


def _apply_message_to_registry(
    registry: SimplexTargetRegistry, normalized: dict[str, Any]
) -> None:
    """Update the per-chat live state after a message was received."""
    chat_ref = normalized.get("chat_ref")
    if not chat_ref:
        return

    target = registry.by_ref(chat_ref)
    if target is None:
        # A chat we did not know about yet (first message from a contact
        # that was neither configured nor discovered): register it now so
        # the message is not an orphan.
        name = normalized.get("display_name") or str(chat_ref)
        target, _ = registry.upsert_discovered(
            str(chat_ref), str(name), normalized.get("type"), True
        )

    target.last_message = normalized.get("text")
    target.last_timestamp = normalized.get("timestamp")
    target.last_direction = normalized.get("direction")
    if normalized.get("direction") == "incoming":
        target.unread_count = (target.unread_count or 0) + 1


# ------------------------------------------------------------------
# Services
# ------------------------------------------------------------------


def _register_services(hass: HomeAssistant) -> None:
    """Register domain services."""

    async def handle_send_message(call: ServiceCall) -> None:
        alias = call.data.get("alias")
        message = call.data["message"]
        title = call.data.get("title")
        chat_ref = call.data.get("chat_ref")
        data = _get_entry_data_for_alias(hass, alias) if alias else _get_entry_data(
            hass, call.data.get("entry_id")
        )
        client: SimplexWsClient = data["client"]
        if not chat_ref:
            if not alias:
                raise HomeAssistantError("Either 'alias' or 'chat_ref' is required")
            chat_ref = data["targets"][alias].get("chat_ref")
        if not chat_ref:
            raise HomeAssistantError(f"Alias '{alias}' has no chat_ref")
        full = f"{title}: {message}" if title else message
        try:
            await client.send_text(chat_ref, full)
        except SimplexWsError as err:
            raise HomeAssistantError(str(err)) from err

    async def handle_send_file(call: ServiceCall) -> None:
        alias = call.data.get("alias")
        chat_ref = call.data.get("chat_ref")
        file_path = call.data["file_path"]
        data = _get_entry_data_for_alias(hass, alias) if alias else _get_entry_data(
            hass, call.data.get("entry_id")
        )
        client: SimplexWsClient = data["client"]
        if not chat_ref:
            if not alias:
                raise HomeAssistantError("Either 'alias' or 'chat_ref' is required")
            chat_ref = data["targets"][alias].get("chat_ref")
        if not chat_ref:
            raise HomeAssistantError(f"Alias '{alias}' has no chat_ref")
        if not await hass.async_add_executor_job(Path(file_path).is_file):
            raise HomeAssistantError(f"File not found: {file_path}")
        try:
            await client.send_file(chat_ref, file_path, text=call.data.get("message", ""))
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

    async def handle_list_groups(call: ServiceCall) -> dict[str, Any]:
        entry_id = call.data.get("entry_id")
        data = _get_entry_data(hass, entry_id)
        client: SimplexWsClient = data["client"]
        try:
            groups = await client.list_groups()
        except SimplexWsError as err:
            raise HomeAssistantError(str(err)) from err
        return {"groups": groups}

    async def handle_refresh_contacts(call: ServiceCall) -> dict[str, Any]:
        """Re-run the auto-discovery and return the resulting target list."""
        entry_id = call.data.get("entry_id")
        data = _get_entry_data(hass, entry_id)
        client: SimplexWsClient = data["client"]
        registry: SimplexTargetRegistry | None = data.get("registry")
        entry: ConfigEntry = data["entry"]
        if registry is None:
            raise HomeAssistantError("SimpleX target registry is not available")
        try:
            await _refresh_targets(hass, entry, client, registry)
        except SimplexWsError as err:
            raise HomeAssistantError(str(err)) from err
        return {
            "targets": registry.all(),
            "contacts": len(registry.configured),
            "discovered": len(registry.discovered),
        }

    async def handle_mark_read(call: ServiceCall) -> dict[str, Any]:
        """Mark the items of a chat as read on the SimpleX side."""
        alias = call.data.get("alias")
        chat_ref = call.data.get("chat_ref")
        item_ids = call.data.get("item_ids") or []
        data = _get_entry_data_for_alias(hass, alias) if alias else _get_entry_data(
            hass, call.data.get("entry_id")
        )
        client: SimplexWsClient = data["client"]
        if not chat_ref:
            if not alias:
                raise HomeAssistantError("Either 'alias' or 'chat_ref' is required")
            chat_ref = data["targets"][alias].get("chat_ref")
        if not chat_ref:
            raise HomeAssistantError(f"Alias '{alias}' has no chat_ref")
        if not item_ids:
            raise HomeAssistantError("'item_ids' is required")
        try:
            await client.mark_chat_read(chat_ref, list(item_ids))
        except SimplexWsError as err:
            raise HomeAssistantError(str(err)) from err
        registry: SimplexTargetRegistry | None = data.get("registry")
        if registry is not None:
            registry.update_state(chat_ref, unread_count=0)
        return {"chat_ref": chat_ref, "item_ids": list(item_ids)}

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
                vol.Optional("alias"): cv.string,
                vol.Optional("chat_ref"): cv.string,
                vol.Required("message"): cv.string,
                vol.Optional("title"): cv.string,
                vol.Optional("entry_id"): cv.string,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_FILE,
        handle_send_file,
        schema=vol.Schema(
            {
                vol.Optional("alias"): cv.string,
                vol.Optional("chat_ref"): cv.string,
                vol.Required("file_path"): cv.string,
                vol.Optional("message"): cv.string,
                vol.Optional("entry_id"): cv.string,
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
        SERVICE_LIST_GROUPS,
        handle_list_groups,
        schema=vol.Schema({vol.Optional("entry_id"): cv.string}),
        supports_response=True,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH_CONTACTS,
        handle_refresh_contacts,
        schema=vol.Schema({vol.Optional("entry_id"): cv.string}),
        supports_response=True,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_MARK_READ,
        handle_mark_read,
        schema=vol.Schema(
            {
                vol.Optional("alias"): cv.string,
                vol.Optional("chat_ref"): cv.string,
                vol.Required("item_ids"): vol.All(cv.ensure_list, [cv.positive_int]),
                vol.Optional("entry_id"): cv.string,
            }
        ),
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
