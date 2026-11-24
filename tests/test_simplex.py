"""Unit tests for the SimpleX Chat integration.

The reference frames used here are the *real* ones captured from SimpleX
Chat CLI 7.1.4.0 during the validation run of
https://github.com/MX10-AC2N/simplex-bridge (tests/ws-validate.py, T13
"Replay"). They are the ground truth for the wire format, so replaying
them through the integration's mapping catches any divergence in the
serialisation (a field moving, an item id changing place, …) *before* it
reaches a production Home Assistant.

Run with::

    python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ha_stubs  # noqa: E402

ha_stubs.install()

from custom_components.simplex import (  # noqa: E402
    _apply_message_to_registry,
    _refresh_targets,
    legacy_entity_id_to_new,
    normalize_chat_item,
)
from custom_components.simplex.mapping import (  # noqa: E402
    pending_incoming_file_id,
    resolve_media_url,
)
from custom_components.simplex.targets import (  # noqa: E402
    SimplexTargetRegistry,
    chat_ref_key,
    sanitize_alias,
)

# --------------------------------------------------------------------------
# Real CLI v7.1.4.0 frames
# --------------------------------------------------------------------------
# Captured during the validation run of
# https://github.com/MX10-AC2N/simplex-bridge (tests/ws-validate.py, T13
# "Replay"), stored verbatim in tests/data/cli_v7_replay_frames.json.
#
# One upstream correction: the frame carrying the `chatBanner` /
# `rcvDirectE2EEInfo` items had one `}` too many in the bridge's own
# REPLAY_FRAMES literal, so it was not valid JSON. The bridge's T13 test
# skips malformed frames (it wraps json.loads in a try/except), which means
# the "system items must be filtered" assertion never actually ran on real
# data. The frame is corrected here, so this suite really does cover it.

with open(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "cli_v7_replay_frames.json"),
    encoding="utf-8",
) as _fh:
    REPLAY_FRAMES = json.load(_fh)


def replay_items():
    """Yield every chat item of every replayed frame."""
    for raw in REPLAY_FRAMES:
        resp = json.loads(raw).get("resp", {})
        if resp.get("type") != "newChatItems":
            continue
        for item in resp.get("chatItems") or []:
            yield item


class TestReplayRealCliFrames(unittest.TestCase):
    """The mapping must stay locked on the real CLI v7 serialisation."""

    def setUp(self) -> None:
        self.targets: dict = {}

    def test_no_exception_on_any_item(self) -> None:
        """Regression: the mapping used to raise NameError on EVERY item.

        `item_id` was read from an undefined variable (`ci`), so every
        incoming message died with a NameError, was swallowed by the event
        handler, and no Home Assistant event was ever fired.
        """
        for item in replay_items():
            # Must not raise.
            normalize_chat_item(item, self.targets)

    def test_system_items_are_filtered(self) -> None:
        """chatBanner / rcvDirectE2EEInfo are protocol noise, not bubbles."""
        rendered = [
            normalize_chat_item(item, self.targets)
            for item in replay_items()
        ]
        texts = [r["text"] for r in rendered if r is not None]
        self.assertNotIn("chat banner", texts)
        self.assertNotIn("E2EE info", texts)
        self.assertEqual(len([r for r in rendered if r is not None]), 2)

    def test_item_id_comes_from_chat_item_level(self) -> None:
        """`itemId` lives on `chatItem`, not on `chatItem.meta`."""
        ids = {
            r["item_id"]
            for r in (normalize_chat_item(i, self.targets) for i in replay_items())
            if r is not None
        }
        self.assertEqual(ids, {16, 17})

    def test_direction_is_derived_from_chat_dir(self) -> None:
        directions = {
            r["item_id"]: r["direction"]
            for r in (normalize_chat_item(i, self.targets) for i in replay_items())
            if r is not None
        }
        self.assertEqual(directions[16], "outgoing")
        self.assertEqual(directions[17], "incoming")

    def test_text_is_extracted_from_meta_item_text(self) -> None:
        texts = {
            r["item_id"]: r["text"]
            for r in (normalize_chat_item(i, self.targets) for i in replay_items())
            if r is not None
        }
        self.assertEqual(texts[17], "Alors tu reçois")
        self.assertEqual(texts[16], "ping de validation ws-validate.py")

    def test_chat_ref_is_built_from_the_contact_id(self) -> None:
        for result in (
            normalize_chat_item(i, self.targets) for i in replay_items()
        ):
            if result is not None:
                self.assertEqual(result["chat_ref"], "@3")
                self.assertEqual(result["type"], "contact")
                self.assertEqual(result["display_name"], "AC2N")

    def test_unconfigured_contact_gets_a_name_fallback(self) -> None:
        """An unknown chat must not be an orphan: it gets a stable alias."""
        result = normalize_chat_item(next(replay_items()), self.targets)
        # The first frame item is the chat banner -> filtered.
        self.assertIsNone(result)

        incoming = [
            normalize_chat_item(item, self.targets)
            for item in replay_items()
        ]
        incoming = [r for r in incoming if r is not None]
        self.assertTrue(all(r["alias"] for r in incoming))
        self.assertEqual(incoming[0]["alias"], "ac2n")

    def test_configured_alias_wins_over_the_fallback(self) -> None:
        targets = {"maman": {"chat_ref": "@3", "name": "Maman", "type": "contact"}}
        incoming = [
            normalize_chat_item(item, targets)
            for item in replay_items()
        ]
        incoming = [r for r in incoming if r is not None]
        self.assertTrue(all(r["alias"] == "maman" for r in incoming))


class TestNormalizeEdgeCases(unittest.TestCase):
    """Shapes the CLI may produce that are not in the reference run."""

    def test_legacy_flat_shape_still_supported(self) -> None:
        flat = {
            "itemId": 42,
            "meta": {"direction": "directSnd", "itemText": "bonjour"},
            "msgContent": {"type": "text", "text": "bonjour"},
        }
        result = normalize_chat_item(flat, {})
        self.assertIsNotNone(result)
        self.assertEqual(result["text"], "bonjour")
        self.assertEqual(result["direction"], "outgoing")
        self.assertEqual(result["item_id"], 42)

    def test_group_chat(self) -> None:
        item = {
            "chatInfo": {
                "type": "group",
                "groupInfo": {"groupId": 7, "localDisplayName": "Famille"},
            },
            "chatItem": {
                "itemId": 9,
                "meta": {"chatDir": {"type": "groupRcv"}, "itemText": "coucou"},
                "content": {"type": "text"},
            },
        }
        result = normalize_chat_item(item, {})
        self.assertEqual(result["chat_ref"], "#7")
        self.assertEqual(result["type"], "group")
        self.assertEqual(result["alias"], "famille")
        self.assertEqual(result["direction"], "incoming")

    def test_group_message_exposes_its_sender(self) -> None:
        """A group bubble must show WHO wrote it, not just the group name.

        `display_name` is the *chat* name; the sender lives in
        `chatDir.groupMember` (CIDirection GroupRcv).
        """
        item = {
            "chatInfo": {
                "type": "group",
                "groupInfo": {"groupId": 7, "localDisplayName": "Famille"},
            },
            "chatItem": {
                "itemId": 10,
                "meta": {
                    "chatDir": {
                        "type": "groupRcv",
                        "groupMember": {
                            "groupMemberId": 3,
                            "localDisplayName": "Éric",
                            "memberProfile": {"displayName": "Éric"},
                        },
                    },
                    "itemText": "je suis là",
                },
                "content": {"type": "text"},
            },
        }
        result = normalize_chat_item(item, {})
        self.assertEqual(result["sender"], "Éric")
        self.assertEqual(result["display_name"], "Famille")
        self.assertEqual(result["type"], "group")

    def test_direct_message_sender_is_the_contact(self) -> None:
        item = {
            "chatInfo": {
                "type": "direct",
                "contact": {"contactId": 3, "localDisplayName": "AC2N"},
            },
            "chatItem": {
                "itemId": 11,
                "meta": {"chatDir": {"type": "directRcv"}, "itemText": "salut"},
                "content": {"type": "text"},
            },
        }
        result = normalize_chat_item(item, {})
        self.assertEqual(result["sender"], "AC2N")

    def test_outgoing_message_has_no_sender(self) -> None:
        item = {
            "chatInfo": {
                "type": "direct",
                "contact": {"contactId": 3, "localDisplayName": "AC2N"},
            },
            "chatItem": {
                "itemId": 12,
                "meta": {"chatDir": {"type": "directSnd"}, "itemText": "pong"},
                "content": {"type": "text"},
            },
        }
        result = normalize_chat_item(item, {})
        self.assertIsNone(result["sender"])

    def test_documented_chatdir_placement_is_supported(self) -> None:
        """The documented ChatItem type puts `chatDir` above `meta`."""
        item = {
            "chatInfo": {"type": "direct", "contact": {"contactId": 3}},
            "chatItem": {
                "itemId": 5,
                "chatDir": {"type": "directSnd"},
                "meta": {"itemText": "salut", "itemId": 5},
                "content": {"type": "text"},
            },
        }
        result = normalize_chat_item(item, {})
        self.assertEqual(result["direction"], "outgoing")
        self.assertEqual(result["item_id"], 5)

    def test_file_message_exposes_the_file_metadata(self) -> None:
        item = {
            "chatInfo": {"type": "direct", "contact": {"contactId": 3}},
            "chatItem": {
                "itemId": 11,
                "meta": {
                    "chatDir": {"type": "directRcv"},
                    "itemText": "photo",
                    "itemFile": {
                        "fileId": 55,
                        "fileName": "photo.jpg",
                        "fileSize": 1234,
                    },
                },
                "content": {"type": "image"},
            },
        }
        result = normalize_chat_item(item, {})
        self.assertIsNotNone(result["file"])
        self.assertEqual(result["file"]["file_id"], 55)
        self.assertEqual(result["file"]["name"], "photo.jpg")
        self.assertEqual(result["file"]["kind"], "image")

    def test_non_renderable_items_return_none(self) -> None:
        reaction = {
            "chatInfo": {"type": "direct", "contact": {"contactId": 3}},
            "chatItem": {
                "itemId": 12,
                "meta": {"chatDir": {"type": "directRcv"}},
                "content": {"type": "reaction"},
            },
        }
        self.assertIsNone(normalize_chat_item(reaction, {}))

    def test_pending_incoming_file_id(self) -> None:
        item = {
            "chatInfo": {"type": "direct", "contact": {"contactId": 3}},
            "chatItem": {
                "itemId": 12,
                "meta": {
                    "itemFile": {
                        "fileId": 77,
                        "fileStatus": {"type": "rcvPartial"},
                    }
                },
                "content": {"type": "file"},
            },
        }
        self.assertEqual(pending_incoming_file_id(item), 77)

    def test_resolve_media_url_ignores_missing_files(self) -> None:
        self.assertIsNone(
            resolve_media_url({"name": "nope.jpg"}, "/definitely/not/a/dir")
        )


class TestEntityIdMigration(unittest.TestCase):
    """The device was renamed, so the legacy entity ids must be migrated.

    The device used to be named "SimpleX Chat" (slugified `simple_x_chat`),
    while the README and the shipped dashboards have always documented
    `simplex_chat_*` — every dashboard card was therefore showing
    "entity not found".
    """

    def test_legacy_ids_are_mapped(self) -> None:
        self.assertEqual(
            legacy_entity_id_to_new("sensor.simple_x_chat_last_message"),
            "sensor.simplex_chat_last_message",
        )
        self.assertEqual(
            legacy_entity_id_to_new("binary_sensor.simple_x_chat_connection"),
            "binary_sensor.simplex_chat_connection",
        )
        self.assertEqual(
            legacy_entity_id_to_new("notify.simple_x_chat_alice"),
            "notify.simplex_chat_alice",
        )

    def test_current_ids_are_left_alone(self) -> None:
        self.assertIsNone(
            legacy_entity_id_to_new("sensor.simplex_chat_last_message")
        )
        self.assertIsNone(legacy_entity_id_to_new("sensor.alice_last_message"))

    def test_the_documented_ids_match_the_shipped_dashboards(self) -> None:
        """Every entity id used by the dashboards must be the real one."""
        import pathlib

        root = pathlib.Path(__file__).resolve().parent.parent
        dashboards = root / "dashboards"
        referenced: set[str] = set()
        for path in dashboards.glob("*.yaml"):
            text = path.read_text(encoding="utf-8")
            for line in text.splitlines():
                line = line.strip()
                if line.startswith("entity:"):
                    entity_id = line.split("entity:", 1)[1].strip()
                    if entity_id.startswith(("sensor.", "binary_sensor.")):
                        referenced.add(entity_id)
        self.assertTrue(referenced, "no entity referenced by the dashboards")
        for entity_id in referenced:
            self.assertNotIn(
                "simple_x_chat",
                entity_id,
                f"{entity_id} uses the legacy slug, it would not resolve",
            )


class TestAliasHelpers(unittest.TestCase):
    def test_sanitize_alias(self) -> None:
        self.assertEqual(sanitize_alias("AC2N"), "ac2n")
        self.assertEqual(sanitize_alias("Marie Claire"), "marie_claire")
        self.assertEqual(sanitize_alias("Éric"), "eric")
        self.assertEqual(sanitize_alias("!!!"), "chat")
        self.assertEqual(sanitize_alias(""), "chat")

    def test_chat_ref_key(self) -> None:
        self.assertEqual(chat_ref_key("@3"), "at3")
        self.assertEqual(chat_ref_key("#12"), "hash12")


class TestTargetRegistry(unittest.TestCase):
    def test_configured_targets_are_loaded(self) -> None:
        registry = SimplexTargetRegistry(
            {"maman": {"chat_ref": "@3", "name": "Maman", "type": "contact"}}
        )
        self.assertEqual(len(registry.configured), 1)
        self.assertEqual(len(registry.discovered), 0)
        self.assertEqual(registry.resolve_alias("@3"), "maman")

    def test_discovered_contacts_are_registered(self) -> None:
        registry = SimplexTargetRegistry()
        target, created = registry.upsert_discovered("@3", "AC2N", "contact")
        self.assertTrue(created)
        self.assertEqual(target.alias, "ac2n")
        self.assertTrue(target.discovered)
        self.assertEqual(registry.resolve_alias("@3"), "ac2n")

    def test_discovery_is_idempotent(self) -> None:
        registry = SimplexTargetRegistry()
        registry.upsert_discovered("@3", "AC2N", "contact")
        target, created = registry.upsert_discovered("@3", "AC2N", "contact")
        self.assertFalse(created)
        self.assertEqual(len(registry.targets), 1)

    def test_configured_alias_wins_over_a_discovered_one(self) -> None:
        registry = SimplexTargetRegistry(
            {"maman": {"chat_ref": "@3", "name": "Maman", "type": "contact"}}
        )
        target, created = registry.upsert_discovered("@3", "AC2N", "contact")
        self.assertFalse(created)
        self.assertEqual(target.alias, "maman")
        self.assertFalse(target.discovered)

    def test_duplicate_display_names_get_distinct_aliases(self) -> None:
        registry = SimplexTargetRegistry()
        first, _ = registry.upsert_discovered("@3", "Alex", "contact")
        second, _ = registry.upsert_discovered("@4", "Alex", "contact")
        self.assertEqual(first.alias, "alex")
        self.assertEqual(second.alias, "alex_2")
        self.assertNotEqual(first.alias, second.alias)

    def test_merged_view_is_exposed_as_the_option_shape(self) -> None:
        registry = SimplexTargetRegistry(
            {"maman": {"chat_ref": "@3", "name": "Maman", "type": "contact"}}
        )
        registry.upsert_discovered("#7", "Famille", "group")
        merged = registry.all()
        self.assertEqual(set(merged), {"maman", "famille"})
        self.assertEqual(merged["maman"]["chat_ref"], "@3")
        self.assertFalse(merged["maman"]["discovered"])
        self.assertTrue(merged["famille"]["discovered"])


class _FakeBus:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def async_fire(self, event_type: str, data: dict) -> None:
        self.events.append((event_type, data))


class _FakeHass:
    def __init__(self) -> None:
        self.data: dict = {}
        self.bus = _FakeBus()


class _FakeEntry:
    entry_id = "entry-1"


class _FakeClient:
    def __init__(self, contacts: list[dict], groups: list[dict]) -> None:
        self._contacts = contacts
        self._groups = groups

    async def list_contacts(self) -> list[dict]:
        return self._contacts

    async def list_groups(self) -> list[dict]:
        return self._groups


class TestDiscovery(unittest.TestCase):
    """`_refresh_targets` turns the CLI lists into registry entries."""

    def test_contacts_and_groups_are_discovered(self) -> None:
        hass = _FakeHass()
        entry = _FakeEntry()
        registry = SimplexTargetRegistry()
        client = _FakeClient(
            contacts=[
                {"contactId": 3, "localDisplayName": "AC2N", "contactStatus": "active"},
                {"contactId": 4, "localDisplayName": "Maman", "contactStatus": "active"},
            ],
            groups=[{"groupId": 7, "localDisplayName": "Famille"}],
        )
        created = asyncio.run(
            _refresh_targets(hass, entry, client, registry)  # type: ignore[arg-type]
        )
        self.assertTrue(created)
        self.assertEqual(len(registry.discovered), 3)
        self.assertEqual(registry.resolve_alias("@3"), "ac2n")
        self.assertEqual(registry.resolve_alias("#7"), "famille")

    def test_deleted_contacts_are_skipped(self) -> None:
        hass = _FakeHass()
        registry = SimplexTargetRegistry()
        client = _FakeClient(
            contacts=[
                {"contactId": 3, "localDisplayName": "AC2N", "contactStatus": "active"},
                {"contactId": 4, "localDisplayName": "Ghost", "contactStatus": "deleted"},
            ],
            groups=[],
        )
        asyncio.run(
            _refresh_targets(hass, _FakeEntry(), client, registry)  # type: ignore[arg-type]
        )
        self.assertEqual(len(registry.discovered), 1)
        self.assertIsNone(registry.resolve_alias("@4"))

    def test_merged_targets_are_published_to_the_entry_data(self) -> None:
        hass = _FakeHass()
        entry = _FakeEntry()
        registry = SimplexTargetRegistry(
            {"maman": {"chat_ref": "@3", "name": "Maman", "type": "contact"}}
        )
        hass.data["simplex"] = {entry.entry_id: {"targets": {}, "registry": registry}}
        client = _FakeClient(
            contacts=[{"contactId": 9, "localDisplayName": "Alex"}], groups=[]
        )
        asyncio.run(
            _refresh_targets(hass, entry, client, registry)  # type: ignore[arg-type]
        )
        published = hass.data["simplex"][entry.entry_id]["targets"]
        self.assertEqual(set(published), {"maman", "alex"})


class TestRegistryStateUpdates(unittest.TestCase):
    def test_incoming_message_updates_the_chat_state(self) -> None:
        registry = SimplexTargetRegistry()
        registry.upsert_discovered("@3", "AC2N", "contact")
        _apply_message_to_registry(
            registry,
            {
                "chat_ref": "@3",
                "text": "Alors tu reçois",
                "direction": "incoming",
                "timestamp": 1700000000,
            },
        )
        target = registry.by_ref("@3")
        assert target is not None
        self.assertEqual(target.last_message, "Alors tu reçois")
        self.assertEqual(target.unread_count, 1)

    def test_outgoing_message_does_not_increase_the_unread_counter(self) -> None:
        registry = SimplexTargetRegistry()
        registry.upsert_discovered("@3", "AC2N", "contact")
        _apply_message_to_registry(
            registry,
            {
                "chat_ref": "@3",
                "text": "pong",
                "direction": "outgoing",
                "timestamp": 1700000001,
            },
        )
        target = registry.by_ref("@3")
        assert target is not None
        self.assertEqual(target.unread_count, 0)
        self.assertEqual(target.last_message, "pong")

    def test_an_unknown_chat_is_registered_on_the_fly(self) -> None:
        """A message from a chat we never knew about is not an orphan."""
        registry = SimplexTargetRegistry()
        _apply_message_to_registry(
            registry,
            {
                "chat_ref": "@42",
                "display_name": "Nouveau",
                "type": "contact",
                "text": "salut",
                "direction": "incoming",
            },
        )
        target = registry.by_ref("@42")
        assert target is not None
        self.assertEqual(target.alias, "nouveau")
        self.assertEqual(target.unread_count, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
