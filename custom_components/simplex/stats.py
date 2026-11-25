"""Activity statistics for the SimpleX chats.

SimpleX does not expose any aggregate counters: the CLI only returns chat
items. This module turns those items into the numbers a dashboard wants:
messages received per day, per chat, over a given window.

The counters live on the :class:`~.targets.SimplexTarget` objects (so a
chat and its activity stay together), and the helpers here are pure
functions over them — which keeps them unit-testable without Home
Assistant.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable

from .mapping import unwrap_chat_item
from .targets import SimplexTarget

# How many days the daily series keeps.
DEFAULT_WINDOW_DAYS = 30


def parse_timestamp(value: Any) -> datetime | None:
    """Parse a CLI timestamp (ISO-8601 string) into a datetime.

    The CLI v7 returns UTC ISO-8601 strings (``2026-11-24T07:23:57.123Z``).
    Naive values are assumed to be UTC as well.
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def day_key(value: Any) -> str | None:
    """Return the ``YYYY-MM-DD`` key of a timestamp (in local time)."""
    parsed = parse_timestamp(value)
    if parsed is None:
        return None
    return parsed.astimezone().date().isoformat()


def today_key() -> str:
    """Return today's ``YYYY-MM-DD`` key, in local time."""
    return date.today().isoformat()


def window_keys(days: int = DEFAULT_WINDOW_DAYS) -> list[str]:
    """Return the last ``days`` day keys, oldest first."""
    span = max(1, int(days))
    today = date.today()
    return [(today - timedelta(days=offset)).isoformat() for offset in range(span - 1, -1, -1)]


def record_message(target: SimplexTarget, timestamp: Any) -> bool:
    """Count one received message on a target. Returns True when counted."""
    key = day_key(timestamp)
    if key is None:
        # A message without a usable timestamp still counts, but not in a
        # day bucket — the global total is bumped, the daily series is not.
        target.messages_total += 1
        return False
    target.daily_counts[key] = target.daily_counts.get(key, 0) + 1
    target.messages_total += 1
    return True


def seed_from_items(target: SimplexTarget, items: Iterable[dict[str, Any]]) -> int:
    """Count a batch of already-stored messages on a target.

    Used to back-fill the counters from the chat history at start-up, so
    the statistics are meaningful straight away instead of only counting
    what arrives while Home Assistant is running.

    The items come from `/chats` and `/_get chat`, which wrap every item
    as ``{"chatInfo": {...}, "chatItem": {...}}`` — the timestamp lives in
    ``chatItem.meta.itemTs``. The flat legacy shape is accepted too.

    Returns the number of messages counted.
    """
    counted = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        _, chat_item = unwrap_chat_item(item)
        if not chat_item:
            continue
        meta = chat_item.get("meta") if isinstance(chat_item.get("meta"), dict) else {}
        timestamp = meta.get("itemTs") or meta.get("createdAt")
        record_message(target, timestamp)
        counted += 1
    return counted


def total_for(target: SimplexTarget, days: int | None = None) -> int:
    """Number of messages received on a target, over the last ``days``."""
    if days is None:
        return target.messages_total
    keys = set(window_keys(days))
    return sum(count for key, count in target.daily_counts.items() if key in keys)


def daily_series(
    targets: Iterable[SimplexTarget], days: int = DEFAULT_WINDOW_DAYS
) -> list[dict[str, Any]]:
    """Return the messages received per day, oldest first.

    Every day of the window is present (with 0 when nothing arrived), so a
    chart does not have to fill the gaps itself.
    """
    keys = window_keys(days)
    buckets: dict[str, int] = {key: 0 for key in keys}
    for target in targets:
        for key, count in target.daily_counts.items():
            if key in buckets:
                buckets[key] += count
    return [{"date": key, "count": buckets[key]} for key in keys]


def per_chat(
    targets: Iterable[SimplexTarget], days: int | None = None
) -> list[dict[str, Any]]:
    """Return the per-chat breakdown, busiest first."""
    rows = []
    for target in targets:
        rows.append(
            {
                "alias": target.alias,
                "chat_ref": target.chat_ref,
                "name": target.name,
                "type": target.type,
                "count": total_for(target, days),
                "total": target.messages_total,
                "unread": target.unread_count,
            }
        )
    rows.sort(key=lambda row: (row["count"], row["total"]), reverse=True)
    return rows


def summary(targets: Iterable[SimplexTarget], days: int = DEFAULT_WINDOW_DAYS) -> dict[str, Any]:
    """Return the full activity summary used by the service and the sensors."""
    target_list = list(targets)
    today = today_key()
    return {
        "days": days,
        "today": today,
        "total_today": sum(t.daily_counts.get(today, 0) for t in target_list),
        "total_window": sum(total_for(t, days) for t in target_list),
        "total_all_time": sum(t.messages_total for t in target_list),
        "daily": daily_series(target_list, days),
        "by_chat": per_chat(target_list, days),
    }
