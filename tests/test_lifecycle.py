"""Regression tests for the connection lifecycle (dependency-free, like the rest).

Covers:
  * `accept_invite_link` must wait through a normal event handler instead of
    reading the shared event queue (it used to swallow other contacts'
    connection events for up to 60 s);
  * auto-discovery must skip groups we left / were removed from, accept the
    `[GroupInfo, GroupSummary]` pair shape and report a failed listing;
  * a deleted contact / left group is marked as gone, and comes back when the
    CLI reports it connected again.
"""

from __future__ import annotations

import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ha_stubs  # noqa: E402

ha_stubs.install()

from custom_components.simplex import (  # noqa: E402
    _handle_contact_event,
    _refresh_targets,
)
from custom_components.simplex.targets import SimplexTargetRegistry  # noqa: E402
from custom_components.simplex.websocket_client import (  # noqa: E402
    SimplexWsClient,
    SimplexWsError,
    SimplexWsTimeoutError,
)
from test_simplex import _FakeClient, _FakeEntry, _FakeHass  # noqa: E402


def _client_with_script(loop, on_connect):
    """A client whose RPC layer is scripted (no socket involved)."""
    client = SimplexWsClient("ws://test", loop)

    async def fake_rpc(cmd, timeout=30.0):
        if cmd == "/user":
            return {"type": "activeUser", "user": {"userId": 1}}
        if cmd.startswith("/_connect"):
            on_connect()
            return {"type": "sentConfirmation"}
        raise SimplexWsError("unexpected command", payload={"cmd": cmd})

    client._rpc_cmd = fake_rpc  # type: ignore[method-assign]
    return client


def _event(etype: str, **fields) -> dict:
    return {"resp": {"type": etype, **fields}}


class TestAcceptInviteDoesNotStarveListeners(unittest.TestCase):
    def test_other_handlers_still_see_every_event(self) -> None:
        async def scenario():
            loop = asyncio.get_running_loop()
            client = None

            def emit():
                loop.call_later(0.02, client._dispatch_event, _event("newChatItems", chatItems=[]))
                loop.call_later(
                    0.04,
                    client._dispatch_event,
                    _event("contactConnected", contact={"contactId": 9}),
                )
                # A different contact connecting right after must not be lost.
                loop.call_later(
                    0.06,
                    client._dispatch_event,
                    _event("contactConnected", contact={"contactId": 10}),
                )

            client = _client_with_script(loop, emit)
            seen: list[tuple[str, int | None]] = []
            client.add_event_handler(
                lambda e: seen.append(
                    (e["resp"]["type"], (e["resp"].get("contact") or {}).get("contactId"))
                )
            )
            baseline = len(client._event_handlers)
            result = await client.accept_invite_link("simplex:/invitation#/?v=2", timeout=2)
            await asyncio.sleep(0.1)  # let the remaining scheduled events fire
            return result, seen, baseline, len(client._event_handlers)

        result, seen, baseline, after = asyncio.run(scenario())
        self.assertEqual(result["chat_ref"], "@9")
        self.assertEqual(result["type"], "contact")
        self.assertEqual(
            seen,
            [("newChatItems", None), ("contactConnected", 9), ("contactConnected", 10)],
            "every event must reach the regular handlers, in order",
        )
        self.assertEqual(after, baseline, "the temporary waiter must be unregistered")

    def test_group_join_resolves_to_a_group_ref(self) -> None:
        async def scenario():
            loop = asyncio.get_running_loop()
            client = None

            def emit():
                loop.call_later(
                    0.02,
                    client._dispatch_event,
                    _event("userJoinedGroup", groupInfo={"groupId": 4}),
                )

            client = _client_with_script(loop, emit)
            return await client.accept_invite_link("simplex:/contact#/?v=2", timeout=2)

        result = asyncio.run(scenario())
        self.assertEqual((result["chat_ref"], result["type"]), ("#4", "group"))

    def test_timeout_cleans_up_and_raises(self) -> None:
        async def scenario():
            client = _client_with_script(asyncio.get_running_loop(), lambda: None)
            baseline = len(client._event_handlers)
            with self.assertRaises(SimplexWsTimeoutError):
                await client.accept_invite_link("simplex:/invitation#/?v=2", timeout=0.1)
            return baseline, len(client._event_handlers)

        baseline, after = asyncio.run(scenario())
        self.assertEqual(after, baseline)


class TestDiscoveryRobustness(unittest.TestCase):
    def _refresh(self, client, registry=None):
        registry = registry or SimplexTargetRegistry()
        asyncio.run(_refresh_targets(_FakeHass(), _FakeEntry(), client, registry))  # type: ignore[arg-type]
        return registry

    def test_groups_we_left_or_were_removed_from_are_skipped(self) -> None:
        def group(gid, name, status):
            return {"groupId": gid, "localDisplayName": name, "membership": {"memberStatus": status}}

        registry = self._refresh(
            _FakeClient(
                contacts=[],
                groups=[
                    group(1, "Famille", "member"),
                    group(2, "Ancien", "left"),
                    group(3, "Vire", "removed"),
                    group(4, "Supprime", "group_deleted"),
                    group(5, "Admin", "owner"),
                ],
            )
        )
        self.assertEqual(sorted(t.chat_ref for t in registry.discovered), ["#1", "#5"])

    def test_group_summary_pairs_are_accepted(self) -> None:
        registry = self._refresh(
            _FakeClient(
                contacts=[],
                groups=[[{"groupId": 7, "localDisplayName": "Famille"}, {"currentMembers": 3}]],  # type: ignore[list-item]
            )
        )
        self.assertEqual(registry.resolve_alias("#7"), "famille")

    def test_a_failed_listing_is_reported_not_silent(self) -> None:
        class Failing(_FakeClient):
            async def list_groups(self):
                raise SimplexWsError("boom")

        with self.assertLogs("custom_components.simplex", level="WARNING") as logs:
            registry = self._refresh(
                Failing(contacts=[{"contactId": 3, "localDisplayName": "AC2N"}], groups=[])
            )
        self.assertIn("boom", "\n".join(logs.output))
        self.assertEqual(registry.resolve_alias("@3"), "ac2n")  # the other half still works


class TestChatGone(unittest.TestCase):
    def _setup(self):
        hass, entry = _FakeHass(), _FakeEntry()
        registry = SimplexTargetRegistry()
        hass.data["simplex"] = {entry.entry_id: {"targets": {}, "registry": registry}}
        return hass, entry, registry

    def test_contact_deleted_then_reconnected(self) -> None:
        hass, entry, registry = self._setup()
        contact = {"contactId": 3, "localDisplayName": "AC2N"}
        _handle_contact_event(hass, entry, registry, {"type": "contactConnected", "contact": contact})  # type: ignore[arg-type]
        self.assertTrue(registry.by_ref("@3").connected)

        _handle_contact_event(hass, entry, registry, {"type": "contactDeleted", "contact": contact})  # type: ignore[arg-type]
        self.assertFalse(registry.by_ref("@3").connected)

        _handle_contact_event(hass, entry, registry, {"type": "contactConnected", "contact": contact})  # type: ignore[arg-type]
        self.assertTrue(registry.by_ref("@3").connected)

    def test_leaving_a_group_marks_it_gone(self) -> None:
        hass, entry, registry = self._setup()
        group = {"groupId": 7, "localDisplayName": "Famille"}
        _handle_contact_event(hass, entry, registry, {"type": "userJoinedGroup", "groupInfo": group})  # type: ignore[arg-type]
        self.assertTrue(registry.by_ref("#7").connected)
        _handle_contact_event(hass, entry, registry, {"type": "leftMemberUser", "groupInfo": group})  # type: ignore[arg-type]
        self.assertFalse(registry.by_ref("#7").connected)


if __name__ == "__main__":
    unittest.main()
