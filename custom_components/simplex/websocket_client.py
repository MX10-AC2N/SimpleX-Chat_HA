"""Async WebSocket client for SimpleX Chat CLI bot API."""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
import time
from collections.abc import Callable
from typing import Any

from aiohttp import ClientError, ClientSession, ClientWebSocketResponse, WSMsgType

_LOGGER = logging.getLogger(__name__)

RECONNECT_MIN_DELAY = 1.0
RECONNECT_MAX_DELAY = 60.0


class SimplexWsError(Exception):
    """Base error for SimpleX WebSocket operations."""

    def __init__(
        self,
        message: str,
        reason: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.reason = reason
        self.payload = payload or {}


class SimplexWsTimeoutError(SimplexWsError):
    """Raised when an RPC times out."""


_CONNECTION_READY_EVENTS = frozenset(
    {
        "contactConnected",
        "contactSndReady",
        "userJoinedGroup",
        "groupJoined",
        "startedConnectionToContact",
        "contactConnecting",
    }
)


def _connection_ready_ref(resp: dict[str, Any]) -> tuple[str, str] | None:
    """Return (chat_ref, type) when `resp` announces a usable new chat."""
    etype = resp.get("type")
    if etype not in _CONNECTION_READY_EVENTS:
        return None
    if etype in ("userJoinedGroup", "groupJoined"):
        gid = (resp.get("groupInfo") or resp.get("group") or {}).get("groupId")
        return (f"#{gid}", "group") if gid is not None else None
    cid = (resp.get("contact") or {}).get("contactId")
    return (f"@{cid}", "contact") if cid is not None else None


class SimplexWsClient:
    """Async client for the SimpleX Chat CLI WebSocket API.

    Protocol (see https://github.com/simplex-chat/simplex-chat/blob/stable/bots/README.md):
      - Send:     {"corrId": "...", "cmd": "<command string>"}
      - Response: {"corrId": "...", "resp": {"type": "...", ...}}
      - Events:   {"resp": {"type": "...", ...}}  (no corrId)
    """

    def __init__(self, ws_url: str, loop: asyncio.AbstractEventLoop) -> None:
        self._url = ws_url
        self._loop = loop
        self._session: ClientSession | None = None
        self._ws: ClientWebSocketResponse | None = None
        self._pending: dict[str, asyncio.Future] = {}
        self._events: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._reader_task: asyncio.Task | None = None
        self._reconnect_task: asyncio.Task | None = None
        self._event_dispatcher_task: asyncio.Task | None = None
        self._closing = False
        self._listeners: list[Callable[[bool], None]] = []
        self._event_handlers: list[Callable[[dict[str, Any]], None]] = []
        self._error_listeners: list[Callable[[dict[str, Any]], None]] = []
        self._user_id: int | None = None  # cached active user id
        self._last_error: dict[str, Any] | None = None

    # ------------------------------------------------------------------
    # Connection state
    # ------------------------------------------------------------------

    @property
    def connected(self) -> bool:
        return self._ws is not None and not self._ws.closed

    def add_connection_listener(self, listener: Callable[[bool], None]) -> Callable[[], None]:
        """Register a callback invoked when the connection state changes."""
        self._listeners.append(listener)

        def _remove() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return _remove

    def add_event_handler(self, handler: Callable[[dict[str, Any]], None]) -> Callable[[], None]:
        """Register a handler for unsolicited events (messages, connections…)."""
        self._event_handlers.append(handler)

        def _remove() -> None:
            if handler in self._event_handlers:
                self._event_handlers.remove(handler)

        return _remove

    def add_error_listener(self, listener: Callable[[dict[str, Any]], None]) -> Callable[[], None]:
        """Register a callback invoked when the CLI answers with a chatCmdError."""
        self._error_listeners.append(listener)

        def _remove() -> None:
            if listener in self._error_listeners:
                self._error_listeners.remove(listener)

        return _remove

    @property
    def last_error(self) -> dict[str, Any] | None:
        """The last CLI error (chatCmdError), or None if none happened yet."""
        return dict(self._last_error) if self._last_error else None

    def clear_error(self) -> None:
        """Forget the last error (e.g. after a successful command)."""
        self._last_error = None

    def _record_error(self, resp: dict[str, Any], cmd: str) -> None:
        """Remember the last chatCmdError and notify the error listeners."""
        error = self._convert_chat_cmd_error(resp)
        self._last_error = {
            "message": error.message,
            "reason": error.reason,
            "command": self._redact_cmd(cmd),
            "timestamp": time.time(),
        }
        for listener in list(self._error_listeners):
            try:
                listener(dict(self._last_error))
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Error listener failed")

    def _notify_listeners(self) -> None:
        state = self.connected
        for listener in list(self._listeners):
            try:
                listener(state)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Connection listener failed")

    def _dispatch_event(self, event: dict[str, Any]) -> None:
        for handler in list(self._event_handlers):
            try:
                handler(event)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Event handler failed")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        self._closing = False
        if self._session is None or self._session.closed:
            self._session = ClientSession()
        self._ws = await self._session.ws_connect(self._url, heartbeat=20)
        self._reader_task = self._loop.create_task(self._reader())
        if self._event_dispatcher_task is None or self._event_dispatcher_task.done():
            self._event_dispatcher_task = self._loop.create_task(self._event_dispatcher())

    async def close(self) -> None:
        self._closing = True
        for task in (self._reconnect_task, self._reader_task, self._event_dispatcher_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        if self._ws and not self._ws.closed:
            await self._ws.close()
        if self._session and not self._session.closed:
            await self._session.close()
        self._fail_pending("WebSocket client closed")
        self._notify_listeners()

    def _fail_pending(self, message: str) -> None:
        pending, self._pending = self._pending, {}
        for fut in pending.values():
            if not fut.done():
                fut.set_exception(SimplexWsError(message, reason="connection_lost"))

    # ------------------------------------------------------------------
    # Reader & reconnect
    # ------------------------------------------------------------------

    async def _reader(self) -> None:
        assert self._ws is not None
        try:
            async for msg in self._ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                    except Exception:  # noqa: BLE001
                        _LOGGER.warning("WS reader received non-JSON: %s", msg.data[:200])
                        continue
                    corr = data.get("corrId")
                    if corr and corr in self._pending:
                        fut = self._pending.pop(corr)
                        if not fut.done():
                            fut.set_result(data)
                    else:
                        await self._events.put(data)
                elif msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.ERROR):
                    _LOGGER.debug("WS reader terminating: %s", msg.type)
                    break
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            _LOGGER.debug("WS reader error: %s", exc)

        if self._closing:
            return

        _LOGGER.warning("Connection to SimpleX websocket at %s lost, reconnecting…", self._url)
        if self._ws is not None and not self._ws.closed:
            await self._ws.close()
        self._fail_pending("WebSocket connection lost")
        self._user_id = None  # invalidate cache on disconnect
        self._notify_listeners()
        self._reconnect_task = self._loop.create_task(self._reconnect())

    async def _reconnect(self) -> None:
        delay = RECONNECT_MIN_DELAY
        while not self._closing:
            await asyncio.sleep(delay)
            try:
                await self.connect()
            except (OSError, ClientError, asyncio.TimeoutError) as exc:
                _LOGGER.debug("Reconnect to %s failed: %s; retrying in %.0fs", self._url, exc, delay)
                delay = min(delay * 2, RECONNECT_MAX_DELAY)
                continue
            _LOGGER.info("Reconnected to SimpleX websocket at %s", self._url)
            self._notify_listeners()
            return

    async def _event_dispatcher(self) -> None:
        """Continuously dispatch unsolicited events to registered handlers."""
        while not self._closing:
            try:
                event = await asyncio.wait_for(self._events.get(), timeout=1.0)
                self._dispatch_event(event)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Error in event dispatcher")

    # ------------------------------------------------------------------
    # RPC core
    # ------------------------------------------------------------------

    async def _rpc_cmd(self, cmd: str, timeout: float = 30.0) -> dict[str, Any]:
        if not self.connected:
            raise SimplexWsError(
                "Not connected to the SimpleX websocket",
                reason="not_connected",
                payload={"cmd": cmd},
            )
        assert self._ws is not None

        corr = secrets.token_hex(8)
        payload = {"corrId": corr, "cmd": cmd}
        fut = self._loop.create_future()
        self._pending[corr] = fut

        safe_cmd = self._redact_cmd(cmd)
        _LOGGER.debug("WS → %s (corr=%s)", safe_cmd, corr)

        try:
            await self._ws.send_str(json.dumps(payload))
        except (ConnectionError, ClientError) as exc:
            self._pending.pop(corr, None)
            raise SimplexWsError(
                f"WebSocket connection error: {exc}",
                reason="connection_error",
                payload={"cmd": cmd},
            ) from exc

        try:
            result = await asyncio.wait_for(fut, timeout)
        except asyncio.TimeoutError as exc:
            self._pending.pop(corr, None)
            raise SimplexWsTimeoutError(
                "WebSocket RPC timed out", payload={"cmd": cmd}
            ) from exc
        except Exception:
            self._pending.pop(corr, None)
            raise

        _LOGGER.debug("WS ← corr=%s type=%s", corr, (result.get("resp") or {}).get("type"))

        resp = result.get("resp") if isinstance(result, dict) else None
        if not isinstance(resp, dict):
            return result
        if resp.get("type") == "chatCmdError":
            self._record_error(resp, cmd)
            raise self._convert_chat_cmd_error(resp)
        return resp

    def _redact_cmd(self, cmd: str) -> str:
        """Redact sensitive parts (links, message bodies) from log output."""
        for prefix in ("/_connect", "/connect", "/_send", "/f"):
            if cmd.startswith(prefix + " ") and len(cmd) > len(prefix) + 20:
                head, _, tail = cmd.partition(" ")
                return f"{head} {tail[:20]}…<redacted>…{tail[-6:]}"
        return cmd

    def _convert_chat_cmd_error(self, resp: dict[str, Any]) -> SimplexWsError:
        chat_error = resp.get("chatError") or {}
        message = "SimpleX command error"
        reason = None
        if isinstance(chat_error, dict):
            et = chat_error.get("errorType") or chat_error.get("type")
            if isinstance(et, dict):
                reason = et.get("type") or et.get("message")
                message = et.get("message") or et.get("type") or message
            elif isinstance(et, str):
                reason = et
                message = chat_error.get("message") or et
        return SimplexWsError(message, reason=reason, payload=resp)

    # ------------------------------------------------------------------
    # High-level helpers
    # ------------------------------------------------------------------

    async def get_active_user(self) -> dict[str, Any] | None:
        try:
            resp = await self._rpc_cmd("/user", timeout=10.0)
            if resp.get("type") == "activeUser":
                user = resp.get("user")
                if isinstance(user, dict) and "userId" in user:
                    return user
                _LOGGER.warning("get_active_user: /user response missing userId: %s", resp)
        except SimplexWsError as err:
            _LOGGER.debug("get_active_user: /user failed: %s", err)
        return None

    async def _get_user_id(self) -> int:
        """Return the active user id, caching it for the session."""
        if self._user_id is not None:
            return self._user_id
        user = await self.get_active_user()
        if not user or "userId" not in user:
            raise SimplexWsError(
                "Cannot retrieve active SimpleX user id "
                "(check that the CLI has an active profile)"
            )
        self._user_id = int(user["userId"])
        return self._user_id

    async def accept_invite_link(self, link: str, timeout: float = 60.0) -> dict[str, Any]:
        """Connect via a SimpleX invitation link and return a chat reference when ready.

        Uses the Bot API command `/_connect <userId> <link>` (with JSON fallback
        for older/newer CLI versions). The legacy CLI command `/connect <link>`
        is only tried as a last resort.

        Returns:
            {"chat_ref": "@<contactId>" | "#<groupId>", "type": "contact"|"group",
             "initial": {...}, "event": {...}?}
        """
        link = (link or "").strip()
        if link.startswith("<") and link.endswith(">"):
            link = link[1:-1].strip()
        link = link.strip().strip('"').strip("'")
        _LOGGER.debug("accept_invite_link: start (timeout=%.0fs)", timeout)

        user_id = await self._get_user_id()

        # Listen for the readiness event through a regular event handler, and
        # register it BEFORE sending the command so an event arriving right
        # after the CLI's answer cannot be missed. The previous implementation
        # read the shared event queue directly: for up to `timeout` seconds it
        # competed with the dispatcher, swallowed the connection events of
        # *other* contacts (so the registry never saw them) and re-queued the
        # rest out of order.
        ready: asyncio.Future = self._loop.create_future()

        def _on_ready_event(event: dict[str, Any]) -> None:
            resp = event.get("resp") if isinstance(event, dict) else None
            if ready.done() or not isinstance(resp, dict):
                return
            found = _connection_ready_ref(resp)
            if found:
                ready.set_result((found[0], found[1], resp))

        remove_ready_handler = self.add_event_handler(_on_ready_event)
        try:
            return await self._accept_invite(link, user_id, timeout, ready)
        finally:
            remove_ready_handler()
            if not ready.done():
                ready.cancel()

    async def _accept_invite(
        self, link: str, user_id: int, timeout: float, ready: asyncio.Future
    ) -> dict[str, Any]:
        # Official APIConnect + legacy fallback
        candidates = [
            f"/_connect {user_id} {link}",
            f"/connect {link}",
        ]

        initial: dict[str, Any] | None = None
        last_err: Exception | None = None
        for cmd in candidates:
            try:
                initial = await self._rpc_cmd(cmd, timeout=timeout)
                last_err = None
                _LOGGER.debug("accept_invite_link: command accepted: %s", self._redact_cmd(cmd))
                break
            except SimplexWsError as err:
                last_err = err
                _LOGGER.debug(
                    "accept_invite_link: command failed (%s): %s",
                    cmd.split(" ", 1)[0],
                    err,
                )
                continue
        if initial is None:
            raise last_err or SimplexWsError("Failed to accept invite link")

        # Already known contact
        if initial.get("type") == "contactAlreadyExists":
            contact = initial.get("contact") or {}
            cid = contact.get("contactId")
            if cid is not None:
                return {"chat_ref": f"@{cid}", "type": "contact", "initial": initial}

        if initial.get("type") in ("startedConnectionToContact", "sentInvitationToContact"):
            contact = initial.get("contact") or {}
            cid = contact.get("contactId")
            if cid is not None:
                return {"chat_ref": f"@{cid}", "type": "contact", "initial": initial}

        if initial.get("type") in (
            "sentConfirmation",
            "sentInvitation",
            "contactConnecting",
            "invitation",
        ):
            _LOGGER.debug(
                "accept_invite_link: intermediate type=%s, waiting for connection",
                initial.get("type"),
            )

        try:
            chat_ref, chat_type, event = await asyncio.wait_for(ready, timeout)
        except asyncio.TimeoutError as exc:
            raise SimplexWsTimeoutError(
                "Timed out waiting for connection confirmation after accepting invite"
            ) from exc
        return {"chat_ref": chat_ref, "type": chat_type, "initial": initial, "event": event}

    async def create_invite(self, timeout: float = 15.0) -> str:
        """Create a one-time invitation link (APIAddContact).

        Official syntax (v7.1):
          /_connect <userId>[ incognito=on]

        Response type "invitation" contains:
          connLinkInvitation: { connFullLink: "...", connShortLink: "..."? }
        """
        user_id = await self._get_user_id()

        def _extract_link(resp: dict) -> str | None:
            """Extract a usable invitation / address link from any known response shape."""
            # Official APIAddContact response
            cli = resp.get("connLinkInvitation")
            if isinstance(cli, dict):
                link = cli.get("connFullLink") or cli.get("connShortLink")
                if link:
                    return str(link)
            if isinstance(cli, str) and cli:
                return cli

            for key in ("connLink", "connReqInvitation", "invitation", "connLinkContact"):
                val = resp.get(key)
                if isinstance(val, str) and val:
                    return val
                if isinstance(val, dict):
                    link = val.get("connFullLink") or val.get("connShortLink") or val.get("connLink")
                    if link:
                        return str(link)

            conn = resp.get("connection") or {}
            if isinstance(conn, dict):
                for key in ("connLink", "connLinkInv", "connReqInvitation"):
                    val = conn.get(key)
                    if isinstance(val, str) and val:
                        return val
                    if isinstance(val, dict):
                        link = val.get("connFullLink") or val.get("connShortLink")
                        if link:
                            return str(link)

            ucl = resp.get("userContactLink") or resp.get("contactLink")
            if isinstance(ucl, dict):
                cl = ucl.get("connLinkContact") or ucl
                if isinstance(cl, dict):
                    link = cl.get("connFullLink") or cl.get("connShortLink")
                    if link:
                        return str(link)
                if isinstance(cl, str) and cl:
                    return cl
            return None

        for cmd in (f"/_connect {user_id}", "/connect"):
            try:
                resp = await self._rpc_cmd(cmd, timeout=timeout)
            except SimplexWsError as err:
                _LOGGER.debug("create_invite: %s failed: %s", cmd.split(" ", 1)[0], err)
                continue
            link = _extract_link(resp if isinstance(resp, dict) else {})
            if link:
                return link
            _LOGGER.warning(
                "create_invite: no link in response type=%s keys=%s",
                (resp or {}).get("type"),
                list((resp or {}).keys()),
            )
        raise SimplexWsError("Could not extract invitation link from response")

    async def send_text(self, chat_ref: str, text: str, timeout: float = 30.0) -> dict[str, Any]:
        """Send a plain text message (APISendMessages – official Bot API v7.1).

        Official syntax:
          /_send <chat_ref> json [{"msgContent":{"type":"text","text":"..."}}]
        """
        # `mentions: {}` is part of the officially documented ComposedMessage
        # shape (see simplex-chat-client/typescript/src/client.ts,
        # apiSendTextMessage) — included for parity even though the Haskell
        # field may be optional, since an extra documented field is lower
        # risk than a missing one on CLI versions where it isn't.
        composed = [{"msgContent": {"type": "text", "text": text}, "mentions": {}}]
        cmd = f"/_send {chat_ref} json {json.dumps(composed, separators=(',', ':'))}"
        try:
            return await self._rpc_cmd(cmd, timeout=timeout)
        except SimplexWsError as err:
            _LOGGER.debug("send_text: modern /_send failed (%s), trying legacy CLI syntax", err)
            safe_text = text.replace('"', '\\"')
            legacy_cmd = f'{chat_ref} "{safe_text}"'
            return await self._rpc_cmd(legacy_cmd, timeout=timeout)

    async def send_file(
        self, chat_ref: str, file_path: str, text: str = "", timeout: float = 120.0
    ) -> dict[str, Any]:
        """Send a local file (APISendMessages + fileSource, with /f fallback)."""
        composed = [
            {
                "fileSource": {"filePath": file_path},
                "msgContent": {"type": "file", "text": text or ""},
                "mentions": {},
            }
        ]
        cmd = f"/_send {chat_ref} json {json.dumps(composed, separators=(',', ':'))}"
        try:
            return await self._rpc_cmd(cmd, timeout=timeout)
        except SimplexWsError as err:
            _LOGGER.debug("send_file: modern /_send failed (%s), trying classic /f", err)
            safe_path = file_path.replace('"', '\\"')
            return await self._rpc_cmd(f'/f {chat_ref} "{safe_path}"', timeout=timeout)

    async def list_contacts(self, timeout: float = 15.0) -> list[dict[str, Any]]:
        """Return the list of contacts for the active user.

        Official Bot API (v7.1) — `APIListContacts`:

            /_contacts <userId>

        Response `ContactsList`:

            {"type": "contactsList", "user": {...}, "contacts": [Contact]}

        The legacy CLI command `/contacts` is kept as a fallback for older
        CLIs that do not implement the `/_` API.
        """
        user_id = await self._get_user_id()
        try:
            resp = await self._rpc_cmd(f"/_contacts {user_id}", timeout=timeout)
        except SimplexWsError as err:
            _LOGGER.debug("list_contacts: /_contacts failed (%s), trying legacy /contacts", err)
            resp = await self._rpc_cmd("/contacts", timeout=timeout)
        contacts = resp.get("contacts") or []
        return contacts if isinstance(contacts, list) else []

    async def list_groups(self, timeout: float = 15.0) -> list[dict[str, Any]]:
        """Return the list of groups for the active user.

        Official Bot API (v7.1) — `APIListGroups`:

            /_groups <userId>[@<contactId_>][ <search>]

        Response `GroupsList`:

            {"type": "groupsList", "user": {...}, "groups": [GroupInfo]}

        The legacy CLI command `/groups` is kept as a fallback for older
        CLIs that do not implement the `/_` API.
        """
        user_id = await self._get_user_id()
        try:
            resp = await self._rpc_cmd(f"/_groups {user_id}", timeout=timeout)
        except SimplexWsError as err:
            _LOGGER.debug("list_groups: /_groups failed (%s), trying legacy /groups", err)
            resp = await self._rpc_cmd("/groups", timeout=timeout)
        groups = resp.get("groups") or []
        return groups if isinstance(groups, list) else []

    async def mark_chat_read(
        self, chat_ref: str, item_ids: list[int], timeout: float = 15.0
    ) -> dict[str, Any]:
        """Mark chat items as read.

        Official Bot API (v7.1) — `APIChatItemsRead`:

            /_read chat items <chatRef> <itemId>[,<itemId>...]

        Response `ItemsReadForChat`:

            {"type": "itemsReadForChat", "user": {...}, "chatInfo": {...}}
        """
        if not item_ids:
            return {}
        ids = ",".join(str(int(item_id)) for item_id in item_ids)
        return await self._rpc_cmd(f"/_read chat items {chat_ref} {ids}", timeout=timeout)

    async def get_chats(self, timeout: float = 20.0) -> list[dict[str, Any]]:
        """Return chat previews (one per contact/group) with their recent items.

        Uses `/chats all` (legacy `LastChats` command). Confirmed by reading
        the actual Haskell source of the CLI version pinned in
        mx10-ac2n/simplex-bridge (v7.1.4 — re-checked against v7.0.2 too,
        unchanged between the two, src/Simplex/Chat/Library/Commands.hs):

          ("/chats" <|> "/cs") *> (LastChats <$> (" all" $> Nothing <|> ...))
          LastChats count_ -> ... let count = fromMaybe 5000 count_ ...

        IMPORTANT: bare `/chats` (no argument) parses to `LastChats (Just
        20)` — only the 20 *most recently active* conversations. We
        deliberately always pass `all` (→ capped at 5000 server-side, not
        truly unbounded, but more than any home setup will hit) so a
        household with more than 20 contacts doesn't silently lose the
        older ones from the conversation list / LLM tool / events.
        """
        resp = await self._rpc_cmd("/chats all", timeout=timeout)
        chats = resp.get("chats") or []
        return chats if isinstance(chats, list) else []

    async def get_chat_history(
        self,
        chat_ref: str,
        limit: int = 50,
        before_item_id: int | None = None,
        timeout: float = 20.0,
    ) -> list[dict[str, Any]]:
        """Return up to `limit` chat items for a single contact/group.

        Uses the real per-chat history command `APIGetChat`, confirmed from
        the same source as `get_chats()` above (v7.1.4, re-checked against
        v7.0.2 — unchanged between the two):

          "/_get chat " *> (APIGetChat <$> chatRefP <*> optional (" content=" ...)
            <* A.space <*> chatPaginationP <*> optional (" search=" ...))
          chatPaginationP =
            (CPLast <$ "count=" <*> A.decimal)
              <|> (CPBefore <$ "before=" <*> A.decimal <* A.space <* "count=" <*> A.decimal)
              <|> ...

        i.e. `/_get chat <chatRef> count=<limit>` for the most recent
        `limit` items, or `/_get chat <chatRef> before=<itemId> count=<limit>`
        to page further into the past than `limit` — this is what makes
        real infinite scroll possible (see `ws_api.py`'s `simplex/history`
        command and the chat card's "load older" behaviour).

        Response is `CRApiChat {chat :: AChat, ...}` → JSON `{"type":
        "apiChat", "chat": {"chatInfo", "chatItems", "chatStats"}, ...}`
        (confirmed: `AChat`'s `ToJSON` instance just re-encodes the
        underlying `Chat` record as-is — same shape already used by
        `get_chats()` above).
        """
        cmd = f"/_get chat {chat_ref} "
        cmd += f"before={before_item_id} count={limit}" if before_item_id else f"count={limit}"
        try:
            resp = await self._rpc_cmd(cmd, timeout=timeout)
            chat = resp.get("chat") or {}
            items = chat.get("chatItems") or []
            return items if isinstance(items, list) else []
        except SimplexWsError as err:
            if before_item_id is not None:
                # No fallback for "load older": `/chats` only ever carries
                # the most recent window, it cannot serve a `before=` page.
                raise
            _LOGGER.debug(
                "get_chat_history: /_get chat failed (%s), falling back to /chats all", err
            )
            for chat in await self.get_chats(timeout=timeout):
                info = chat.get("chatInfo") or {}
                contact = info.get("contact") or {}
                group = info.get("groupInfo") or {}
                ref = None
                if contact.get("contactId") is not None:
                    ref = f"@{contact['contactId']}"
                elif group.get("groupId") is not None:
                    ref = f"#{group['groupId']}"
                if ref == chat_ref:
                    items = chat.get("chatItems") or []
                    return items[-limit:] if isinstance(items, list) else []
            return []

    async def receive_file(self, file_id: int, timeout: float = 60.0) -> dict[str, Any]:
        """Accept an incoming file transfer.

        CORRECTED: there is no `/_receive` command — that was a mistaken
        guess carried over from conflating the Haskell *data type* field
        name (`ReceiveFile { fileId, userApprovedRelays, ... }`) with the
        actual CLI *text* command. Confirmed directly from the pinned CLI's
        own source (`src/Simplex/Chat/Library/Commands.hs`, checked against
        the CLI version actually pinned in mx10-ac2n/simplex-bridge
        (v7.1.4 — re-checked against v7.0.2 too, unchanged between the two):

          ("/freceive " <|> "/fr ") *>
            (ReceiveFile <$> A.decimal
                         <*> (" approved_relays=" *> onOffP <|> pure False)
                         <*> optional (" encrypt=" *> onOffP)
                         <*> optional (" inline=" *> onOffP)
                         <*> optional (A.space *> filePath))

        So the on-the-wire parameter is `approved_relays=` (snake_case),
        not `userApprovedRelays` — that name only exists internally/in the
        JSON record and in third-party API bindings describing it, never
        in the text command itself. `/fr` and `/freceive` are the same
        command (short alias), confirmed by the same source line.
        """
        return await self._rpc_cmd(f"/fr {file_id} approved_relays=on", timeout=timeout)

    async def get_user_address(self, timeout: float = 10.0) -> str | None:
        """Return the long-term user address if one exists."""
        try:
            user_id = await self._get_user_id()
        except SimplexWsError:
            return None
        for cmd in (f"/_address {user_id}", f"/_show_address {user_id}", "/address"):
            try:
                resp = await self._rpc_cmd(cmd, timeout=timeout)
            except SimplexWsError as err:
                _LOGGER.debug("get_user_address: %s failed: %s", cmd.split(" ", 1)[0], err)
                continue
            addr = (
                resp.get("contactLink")
                or resp.get("address")
                or resp.get("connLinkContact")
                or (resp.get("userContactLink") or {}).get("connLink")
            )
            if isinstance(addr, dict):
                addr = addr.get("connFullLink") or addr.get("connShortLink")
            if addr:
                return str(addr)
        return None

    async def ensure_bot_profile(self, display_name: str | None = None) -> None:
        """Ensure the active profile has peerType = "bot"."""
        user = await self.get_active_user()
        if not user:
            _LOGGER.warning("ensure_bot_profile: no active user")
            return
        profile = user.get("profile") or {}
        if profile.get("peerType") == "bot":
            return
        new_profile = {
            "displayName": display_name or profile.get("displayName") or "Home Assistant",
            "fullName": profile.get("fullName") or "",
            "peerType": "bot",
        }
        cmd = f"/u {json.dumps(new_profile, separators=(',', ':'))}"
        try:
            await self._rpc_cmd(cmd, timeout=15.0)
            _LOGGER.info("Profile set to peerType=bot")
            self._user_id = None
        except SimplexWsError as err:
            _LOGGER.warning("Failed to set peerType=bot: %s", err)

    async def set_bot_commands(self, commands: str) -> None:
        """Configure the bot command menu (/set bot commands)."""
        commands = (commands or "").strip()
        if not commands:
            return
        await self._rpc_cmd(f"/set bot commands {commands}", timeout=10.0)
        _LOGGER.info("Bot commands applied")
