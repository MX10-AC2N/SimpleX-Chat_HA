# Configuration

## Automatic discovery (recommended)

Nothing to do. On start-up the integration asks the CLI for its contacts
(`/_contacts`) and groups (`/_groups`), and keeps the list up to date from
the connection events (`contactConnected`, `contactSndReady`,
`contactUpdated`, `userJoinedGroup`, …).

Every discovered chat gets:

- a `notify.simplex_chat_<alias>` entity,
- a device with a *Last message*, *Unread messages* and *Connected* entity,
- a row in the *SimpleX Conversations* dashboard card.

> Auto-discovery needs the bridge to accept contact requests automatically
> (`SIMPLEX_AUTO_ACCEPT=true`). See [DOCKER.md](../DOCKER.md).

---

## Aliases

The alias is the short name used everywhere — in entity ids
(`notify.simplex_chat_alice`), in the services (`alias: Alice`) and in the
dashboard cards.

It is derived from the display name (`Éric` → `eric`). To choose your own:

**Settings → Devices & services → SimpleX Chat → Configure → Rename a
contact / group**

A manually configured alias always wins over the auto-derived one.

---

## Manual contacts

1. **Settings → Devices & services → SimpleX Chat → Configure**
2. Choose **Add a contact / group**
3. Enter a friendly alias (e.g. `Alice`, `Family`)
4. Paste a SimpleX invitation link (1:1 or group)
5. A `notify.simplex_chat_alice` entity (or similar) is created automatically

Manual and discovered contacts can be mixed — the integration merges both
into a single view.

---

## How the registry works

The **target registry** (`targets.py`) merges the manually configured chats
and the auto-discovered ones into a single list, so every consumer —
notify entities, sensors, the LLM tool, the dashboard cards — sees the same
contacts.

Discovery is **runtime-only**: it never rewrites the config entry, so no
reload is triggered and nothing is written to the storage. A contact that
disappears from the CLI is marked as gone and comes back as soon as the CLI
reports it connected again.

---

## Unread counters

Unread badges need `SIMPLEX_MARK_READ=false` on the bridge. With `true` the
CLI marks every message as read on arrival and the counters stay at zero.
See [DOCKER.md](../DOCKER.md).

---

## Next steps

- [Send your first message](usage.md)
- [Install a dashboard](dashboards.md)
