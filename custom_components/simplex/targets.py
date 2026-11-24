"""Registry of the SimpleX chats the integration knows about.

Historically the integration required the user to configure *every* chat by
hand ("targets" in the options flow: paste an invitation link, give it an
alias). That made the integration unusable for the common household case:
a family with ten contacts would have to paste ten one-time invitation
links — which are single-use — before a single message could be displayed.

This module holds the merged view of two sources:

  * **configured** targets — explicit, user-named, persisted in the config
    entry options (``alias -> {chat_ref, name, type}``). These always win:
    the alias the user chose is the alias everything else uses.
  * **discovered** targets — auto-registered from the CLI's own contact and
    group lists (``/_contacts`` / ``/_groups``) and from the live
    connection events (``contactConnected``, ``contactSndReady``,
    ``contactUpdated``, ``userJoinedGroup``, …).

Both are exposed as a single flat ``alias -> target`` mapping, so every
consumer (notify entities, sensors, the Assist/LLM tool, the websocket API
behind the Lovelace cards) sees exactly the same set of chats.

The registry is deliberately **runtime-only**: nothing is written back to the
config entry, so discovering a new contact never rewrites the user's
storage and never triggers a reload of the entry.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from .const import DOMAIN

# Aliases end up in entity ids, service call payloads and websocket
# commands, so they are restricted to a conservative character set.
_UNSAFE_ALIAS_RE = re.compile(r"[^a-z0-9_]+")


def sanitize_alias(name: str, fallback: str = "chat") -> str:
    """Turn a human display name into a stable, machine-friendly alias.

    Accents are folded to their ASCII base ("Éric" -> "eric") instead of
    being dropped, so the alias stays readable for non-Latin names.
    """
    decomposed = unicodedata.normalize("NFKD", name or "")
    ascii_only = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    alias = _UNSAFE_ALIAS_RE.sub("_", ascii_only.lower()).strip("_")
    return alias or fallback


def chat_ref_key(chat_ref: str) -> str:
    """Return a filesystem/entity-id-safe key for a chat reference.

    ``@3`` -> ``at3``, ``#12`` -> ``hash12``. Used to build stable unique
    ids for the per-contact entities.
    """
    raw = (chat_ref or "").strip().lower()
    if raw.startswith("@"):
        raw = f"at{raw[1:]}"
    elif raw.startswith("#"):
        raw = f"hash{raw[1:]}"
    return _UNSAFE_ALIAS_RE.sub("_", raw).strip("_") or "unknown"


@dataclass
class SimplexTarget:
    """One chat the integration can send to / receive from."""

    alias: str
    chat_ref: str
    name: str
    type: str = "contact"  # "contact" | "group"
    discovered: bool = False
    connected: bool = False
    unread_count: int = 0
    last_message: str | None = None
    last_timestamp: Any = None
    last_direction: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def as_option(self) -> dict[str, Any]:
        """Return the historic ``targets`` option shape for this target."""
        return {
            "chat_ref": self.chat_ref,
            "name": self.name,
            "type": self.type,
            "discovered": self.discovered,
        }


class SimplexTargetRegistry:
    """Merged view of configured + auto-discovered SimpleX chats."""

    def __init__(self, configured: Mapping[str, Any] | None = None) -> None:
        self._targets: dict[str, SimplexTarget] = {}
        self._by_ref: dict[str, str] = {}
        self.load_configured(configured or {})

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_configured(self, configured: Mapping[str, Any]) -> None:
        """Register the user-configured targets (they take priority)."""
        for alias, data in configured.items():
            if not isinstance(data, Mapping):
                continue
            chat_ref = data.get("chat_ref")
            if not chat_ref:
                continue
            chat_ref = str(chat_ref)
            # A configured alias always wins over an auto-derived one, even
            # if the same chat was already discovered first.
            existing = self._targets.get(alias)
            if existing is not None and existing.chat_ref != chat_ref:
                continue
            target = SimplexTarget(
                alias=alias,
                chat_ref=chat_ref,
                name=str(data.get("name") or alias),
                type=str(data.get("type") or self._guess_type(chat_ref)),
                discovered=False,
                connected=True,
            )
            self._targets[alias] = target
            self._by_ref[chat_ref] = alias

    @staticmethod
    def _guess_type(chat_ref: str) -> str:
        return "group" if chat_ref.startswith("#") else "contact"

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    @property
    def targets(self) -> list[SimplexTarget]:
        """All known targets, configured ones first."""
        return sorted(
            self._targets.values(),
            key=lambda t: (t.discovered, t.alias.lower()),
        )

    @property
    def configured(self) -> list[SimplexTarget]:
        return [t for t in self.targets if not t.discovered]

    @property
    def discovered(self) -> list[SimplexTarget]:
        return [t for t in self.targets if t.discovered]

    def get(self, alias: str) -> SimplexTarget | None:
        return self._targets.get(alias)

    def by_ref(self, chat_ref: str | None) -> SimplexTarget | None:
        if not chat_ref:
            return None
        alias = self._by_ref.get(chat_ref)
        return self._targets.get(alias) if alias else None

    def resolve_alias(self, chat_ref: str | None) -> str | None:
        """Return the alias to use for a chat reference, if it is known."""
        target = self.by_ref(chat_ref)
        return target.alias if target else None

    def all(self) -> dict[str, dict[str, Any]]:
        """Return the merged ``alias -> option`` mapping.

        The shape matches the historic ``targets`` option, so consumers that
        already index ``targets[alias]["chat_ref"]`` keep working unchanged.
        """
        return {alias: target.as_option() for alias, target in self._targets.items()}

    # ------------------------------------------------------------------
    # Writing
    # ------------------------------------------------------------------

    def upsert_discovered(
        self,
        chat_ref: str,
        name: str,
        type_: str | None = None,
        connected: bool = True,
    ) -> tuple[SimplexTarget, bool]:
        """Register an auto-discovered chat.

        Returns ``(target, created)`` where ``created`` is True only when
        the chat was not known before — which is what the entity platforms
        use to decide whether to create new entities.
        """
        chat_ref = str(chat_ref)
        existing = self.by_ref(chat_ref)
        if existing is not None:
            # Known already: refresh the mutable bits only. The alias stays
            # untouched so it remains stable across restarts.
            if existing.discovered:
                if name and existing.name != name:
                    existing.name = name
                if type_:
                    existing.type = type_
            existing.connected = connected
            return existing, False

        alias = self._unique_alias(sanitize_alias(name, fallback=chat_ref_key(chat_ref)))
        target = SimplexTarget(
            alias=alias,
            chat_ref=chat_ref,
            name=name or alias,
            type=type_ or self._guess_type(chat_ref),
            discovered=True,
            connected=connected,
        )
        self._targets[alias] = target
        self._by_ref[chat_ref] = alias
        return target, True

    def _unique_alias(self, base: str) -> str:
        if base not in self._targets:
            return base
        index = 2
        while f"{base}_{index}" in self._targets:
            index += 1
        return f"{base}_{index}"

    def update_state(self, chat_ref: str | None, **kwargs: Any) -> SimplexTarget | None:
        """Update the live state (last message, unread count, …) of a chat."""
        target = self.by_ref(chat_ref)
        if target is None:
            return None
        for key, value in kwargs.items():
            if hasattr(target, key):
                setattr(target, key, value)
        return target

    def remove(self, alias: str) -> bool:
        """Forget a target (used when a contact is deleted)."""
        target = self._targets.pop(alias, None)
        if target is None:
            return False
        if self._by_ref.get(target.chat_ref) == alias:
            del self._by_ref[target.chat_ref]
        return True


def registry_for(hass: Any, entry_id: str) -> SimplexTargetRegistry | None:
    """Return the registry of a config entry, if it is set up."""
    data = hass.data.get(DOMAIN, {}).get(entry_id)
    if isinstance(data, dict):
        registry = data.get("registry")
        if isinstance(registry, SimplexTargetRegistry):
            return registry
    return None


def entry_data_for(hass: Any, entry_id: str | None = None) -> list[dict[str, Any]]:
    """Return the runtime data of every (or one) SimpleX config entry."""
    domain_data = hass.data.get(DOMAIN, {})
    entries = {
        key: value
        for key, value in domain_data.items()
        if isinstance(value, dict) and "client" in value
    }
    if entry_id:
        data = entries.get(entry_id)
        return [data] if data else []
    return list(entries.values())


def merge_targets(*sources: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Merge several ``alias -> option`` mappings (later wins)."""
    merged: dict[str, dict[str, Any]] = {}
    for source in sources:
        for alias, data in (source or {}).items():
            if isinstance(data, Mapping):
                merged[alias] = dict(data)
    return merged
