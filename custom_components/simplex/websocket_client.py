"""Async WebSocket client for SimpleX Chat CLI bot API."""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
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


class SimplexWsClient:
    """Async client for the SimpleX Chat CLI WebSocket API.

    Protocol (see https://github.com/simplex-chat/simplex-chat/blob/stable/bots/README.md):
      - Send:    {"corrId": "...", "cmd": "<command string>"}
      - Response:{"corrId": "...", "resp": {"type": "...", ...}}
      - Events:  {"resp": {"type": "...", ...}}  (no corrId)
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
            raise self._convert_chat_cmd_error(resp)
        return resp

    def _redact_cmd(self, cmd: str) -> str:
        if "connect" in cmd and ("http" in cmd or "simplex:" in cmd):
            parts = cmd.split(" ", 1)
            if len(parts) == 2 and len(parts[1]) > 20:
                link = parts[1]
                return f"{parts[0]} {link[:10]}…<redacted>…{link[-6:]}"
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
                return resp.get("user")
        except SimplexWsError:
            pass
        return None

    async def accept_invite_link(self, link: str, timeout: float = 60.0) -> dict[str, Any]:
        """Connect via a SimpleX link and return a chat reference when ready.

        Returns:
            {"chat_ref": "@<contactId>" | "#<groupId>", "initial": {...}, "event": {...}?}
        """
        link = (link or "").strip()
        # Strip accidental markdown / angle brackets / whitespace from copy-paste
        if link.startswith("<") and link.endswith(">"):
            link = link[1:-1].strip()
        link = link.strip().strip('"').strip("'")
        _LOGGER.debug("accept_invite_link: start (timeout=%.0fs)", timeout)

        # Try quoted first (special chars in #fragment), then unquoted
        safe = link.replace("'", "")
        initial: dict[str, Any]
        last_err: Exception | None = None
        for cmd in (f"/connect '{safe}'", f"/connect {safe}"):
            try:
                initial = await self._rpc_cmd(cmd, timeout=timeout)
                last_err = None
                break
            except SimplexWsError as err:
                last_err = err
                _LOGGER.debug("accept_invite_link: cmd failed (%s): %s", cmd.split(" ", 1)[0], err)
                continue
        if last_err is not None:
            raise last_err

        # Already known contact
        if initial.get("type") == "contactAlreadyExists":
            contact = initial.get("contact") or {}
            cid = contact.get("contactId")
            if cid is not None:
                return {"chat_ref": f"@{cid}", "type": "contact", "initial": initial}

        # Some CLI versions return the contact immediately
        if initial.get("type") in ("contactConnecting", "sentConfirmation", "sentInvitation"):
            contact = initial.get("contact") or {}
            cid = contact.get("contactId")
            # Keep waiting for readiness, but log progress
            _LOGGER.debug("accept_invite_link: intermediate type=%s contactId=%s", initial.get("type"), cid)

        # Wait for a readiness event
        wanted = {
            "contactConnected",
            "contactSndReady",
            "userJoinedGroup",
            "groupJoined",
            "acceptingContactRequest",
            "receivedContactRequest",
        }
        deadline = self._loop.time() + timeout
        while self._loop.time() < deadline:
            try:
                evt = await asyncio.wait_for(self._events.get(), timeout=2.0)
            except asyncio.TimeoutError:
                continue

            resp = evt.get("resp") if isinstance(evt, dict) else None
            if not isinstance(resp, dict):
                continue
            etype = resp.get("type")
            if etype not in wanted:
                # Re-queue unrelated events so other handlers can see them
                await self._events.put(evt)
                continue

            chat_ref: str | None = None
            chat_type = "contact"

            if etype in ("contactConnected", "contactSndReady"):
                contact = resp.get("contact") or {}
                cid = contact.get("contactId")
                if cid is not None:
                    chat_ref = f"@{cid}"
            elif etype in ("userJoinedGroup", "groupJoined"):
                group = resp.get("groupInfo") or resp.get("group") or {}
                gid = group.get("groupId")
                if gid is not None:
                    chat_ref = f"#{gid}"
                    chat_type = "group"

            if chat_ref:
                return {
                    "chat_ref": chat_ref,
                    "type": chat_type,
                    "initial": initial,
                    "event": resp,
                }

        raise SimplexWsTimeoutError(
            "Timed out waiting for connection confirmation after accepting invite"
        )

    async def create_invite(self, timeout: float = 15.0) -> str:
        """Create a one-time invitation link and return the link string."""
        resp = await self._rpc_cmd("/connect", timeout=timeout)
        # Response shapes vary; try common fields
        link = (
            resp.get("connLink")
            or resp.get("invitation")
            or (resp.get("connection") or {}).get("connLink")
            or resp.get("connReqInvitation")
        )
        if not link:
            # Fallback: some versions return the link in a nested structure
            _LOGGER.debug("create_invite response: %s", resp)
            raise SimplexWsError("Could not extract invitation link from response")
        return str(link)

    async def send_text(self, chat_ref: str, text: str, timeout: float = 30.0) -> dict[str, Any]:
        """Send a plain text message to a contact (@id) or group (#id)."""
        # Escape double-quotes inside the message for the CLI command
        safe_text = text.replace('"', '\\"')
        cmd = f'{chat_ref} "{safe_text}"'
        return await self._rpc_cmd(cmd, timeout=timeout)

    async def send_file(
        self, chat_ref: str, file_path: str, timeout: float = 120.0
    ) -> dict[str, Any]:
        """Send a local file (audio clip, video clip, image, …) to a contact or group.

        `file_path` must be readable by the simplex-chat CLI process itself —
        if the CLI runs in a different container/host than Home Assistant,
        it must be a path inside a volume shared between the two.
        """
        safe_path = file_path.replace('"', '\\"')
        cmd = f'/f {chat_ref} "{safe_path}"'
        return await self._rpc_cmd(cmd, timeout=timeout)

    async def list_contacts(self, timeout: float = 15.0) -> list[dict[str, Any]]:
        """Return the list of contacts for the active user."""
        resp = await self._rpc_cmd("/contacts", timeout=timeout)
        # Shape can be {"type": "contactsList", "contacts": [...]}
        contacts = resp.get("contacts") or []
        return contacts if isinstance(contacts, list) else []

    async def get_user_address(self, timeout: float = 10.0) -> str | None:
        """Return the long-term user address if one exists."""
        try:
            resp = await self._rpc_cmd("/address", timeout=timeout)
            addr = resp.get("contactLink") or resp.get("address") or resp.get("connLinkContact")
            return str(addr) if addr else None
        except SimplexWsError:
            return None