# 💬 SimpleX Chat for Home Assistant

[![hacs][hacs-badge]][hacs-url]
[![release][release-badge]][release-url]
![downloads][downloads-badge]

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=MX10-AC2N&repository=SimpleX-Chat_HA)

> 🇫🇷 **Version française** : [README_fr.md](README_fr.md)

---

## What is SimpleX Chat for Home Assistant?

A complete Home Assistant integration to send and receive messages through
[SimpleX Chat][simplex] — the messenger that is private by design: no user
identifiers, end-to-end encryption, minimal metadata.

Use it as a secure notification channel for your home, as a messaging front-end
on a wall tablet, or as a target for voice assistants and AI agents.

### Features

- 🔎 **Auto-discovery** — the CLI's contacts and groups are discovered on the fly; no more pasting a one-time invitation link for every contact
- 🔔 **Native notifications** — one `notify.*` entity per contact or group, created as soon as the bot knows them
- 💬 **Incoming messages** — `simplex_message_received` event + sensors
- 🔍 **Search across every conversation** — one search box over the whole message history
- 🖼️ **Images, audio and video** — sent as real SimpleX content, displayed inline by the clients
- 📊 **Activity statistics** — messages per day and per contact, derived from the history
- ⚡ **Live connection tracking** — a contact accepted while Home Assistant is running shows up immediately, no restart
- 📇 **Per-contact entities** — last message, unread counter and connectivity, on one device per contact/group
- 🧩 **Services** — send message, send file, search, activity stats, create invite, accept link, list chats, refresh, mark as read
- 🤖 **LLM / Assist tools** — `send_simplex_message` and `search_simplex_messages`
- 🔄 **Automatic reconnection** with exponential backoff
- 🌍 **Translations** EN / FR
- 📦 **Ready-to-use dashboards** — 9 of them, from a status wall to an app-like messenger

---

## Requirements

### Required

1. **SimpleX Chat CLI** in WebSocket mode:

   ```bash
   simplex-chat -p 5225
   ```

   When Home Assistant runs in Docker, do **not** use `127.0.0.1` from inside
   the HA container unless both containers share the host network namespace.
   See the dedicated guide: **[DOCKER.md](DOCKER.md)**.

2. Home Assistant **2025.8+** (2026.x recommended).

### Only for the ready-made dashboards

The dashboards in [`dashboards/`](dashboards) are optional — the integration
works on its own. But they are built on two community Lovelace cards, which
you must install first if you use them:

| Dashboard | [Mushroom][mushroom-url] | [Auto Entities][auto-entities-url] | SimpleX cards |
|-----------|--------------------------|-----------------------------------|---------------|
| `simplex_fr.yaml` / `simplex_en.yaml` | – | ✅ required | – |
| `simplex_mushroom_fr.yaml` / `simplex_mushroom_en.yaml` | ✅ **required** | ✅ required | – |
| `simplex_auto_fr.yaml` / `simplex_auto_en.yaml` | – | – | ✅ required |
| `simplex_tablet_fr.yaml` | – | – | ✅ required (intercom) |
| `simplex_android_home_fr.yaml` | – | – | ✅ required |
| `simplex_android_look_fr.yaml` | – | – | ✅ required |

> ⚠️ **`simplex_mushroom_*.yaml` does not render at all without Mushroom.**
> The cards show up as "Custom element: mushroom-…" with an error in the
> browser console. Install it with HACS → *Integrations* → search
> **Mushroom** → download, then reload the resources in
> *Settings → Dashboards → Resources*.

```yaml
# Settings → Dashboards → Resources → Add Resource
url: /local/mushroom.js
type: JavaScript Module
```

The **SimpleX cards** (conversation list, chat view, intercom) ship with this
repository — no HACS needed, you just copy them to `/config/www/` (see
[Installing the custom cards](#installing-the-custom-cards)).

---

## Installation

### HACS (recommended)

1. HACS → Integrations → ⋮ → **Custom repositories**
2. URL: `https://github.com/MX10-AC2N/SimpleX-Chat_HA`
3. Category: **Integration**
4. Download → Restart Home Assistant
5. **Settings → Devices & services → Add integration → SimpleX Chat**
6. Enter the WebSocket URL (default: `ws://127.0.0.1:5225`)

### Manual installation

```bash
cd /config/custom_components
# copy the simplex/ folder from this repository
```

Restart Home Assistant, then add the integration from the UI.

### Docker

If Home Assistant runs in Docker, you **must** run a SimpleX Chat WebSocket
daemon alongside it.

→ Full guide: **[DOCKER.md](DOCKER.md)** (compose examples, networking,
troubleshooting).

The reference daemon is **[MX10-AC2N/simplex-bridge][bridge-url]**, whose
WebSocket contract is validated by a dedicated test suite (T01–T13).

---

## Configuration

### Automatic (recommended)

Nothing to do. On start-up the integration asks the CLI for its contacts
(`/_contacts`) and groups (`/_groups`), and keeps the list up to date from
the connection events (`contactConnected`, `contactSndReady`,
`contactUpdated`, `userJoinedGroup`, …).

Every discovered chat gets:

- a `notify.simplex_chat_<alias>` entity,
- a device with a *Last message*, *Unread messages* and *Connected* entity,
- a row in the *SimpleX Conversations* dashboard card.

The alias is derived from the display name (`Éric` → `eric`). To choose your
own: **Settings → Devices & services → SimpleX Chat → Configure → Rename a
contact / group**.

> Auto-discovery needs the bridge to accept contact requests automatically
> (`SIMPLEX_AUTO_ACCEPT=true`). See [DOCKER.md](DOCKER.md).
>
> Unread badges also need `SIMPLEX_MARK_READ=false` on the bridge: with
> `true` the CLI marks every message as read on arrival and the counters
> stay at zero. See [DOCKER.md](DOCKER.md).

### Manual

1. **Settings → Devices & services → SimpleX Chat → Configure**
2. Choose **Add a contact / group**
3. Enter a friendly alias (e.g. `Alice`, `Family`)
4. Paste a SimpleX invitation link (1:1 or group)
5. A `notify.simplex_chat_alice` entity (or similar) is created automatically

Manual and discovered contacts can be mixed; a manually configured alias
always wins over the auto-derived one.

---

## Usage

### Notifications

```yaml
action: notify.send_message
data:
  message: "Dinner is ready!"
target:
  entity_id: notify.simplex_chat_alice
```

Multiple recipients:

```yaml
target:
  entity_id:
    - notify.simplex_chat_alice
    - notify.simplex_chat_family
```

### Services

#### Send a message

```yaml
action: simplex.send_message
data:
  alias: Alice
  message: "Front door opened"
  title: "Security"
```

By chat reference instead of alias:

```yaml
action: simplex.send_message
data:
  chat_ref: "@3"
  message: "Front door opened"
```

#### Send a file or an image

```yaml
action: simplex.send_file
data:
  alias: Alice
  file_path: /config/simplex_outbox/clip.ogg
  message: "Doorbell recording"   # optional caption
```

The path must be readable by the `simplex-chat` process — use a volume
shared with the bridge container (see [DOCKER.md](DOCKER.md)).

#### Search across every conversation

```yaml
action: simplex.search
data:
  query: "dinner"
  limit: 50
```

#### Activity statistics

```yaml
action: simplex.activity_stats
data:
  days: 30
```

It returns the daily series and the per-chat breakdown (count over the
window, all-time total, unread count).

#### Create an invitation

```yaml
action: simplex.create_invite
```

The response contains `invite_link`.

#### Accept an invitation

```yaml
action: simplex.accept_invite
data:
  invite_link: "https://simplex.chat/invitation#..."
  alias: Bob
```

#### Discover / refresh

```yaml
action: simplex.refresh_contacts
```

Forces a re-read of the CLI's contact and group lists.

#### Mark as read

```yaml
action: simplex.mark_read
data:
  alias: Alice
  item_ids: [17, 18]
```

### Incoming events

Every incoming message fires `simplex_message_received`:

```yaml
automation:
  - alias: "React to a SimpleX message"
    trigger:
      - platform: event
        event_type: simplex_message_received
    condition:
      - condition: template
        value_template: "{{ trigger.event.data.alias == 'Alice' }}"
    action:
      - action: notify.persistent_notification
        data:
          message: "{{ trigger.event.data.text }}"
```

| Key            | Description                                |
|----------------|--------------------------------------------|
| `alias`        | Alias of the chat (configured or derived)  |
| `chat_ref`     | `@123` or `#456`                           |
| `display_name` | Display name of the contact / group        |
| `sender`       | Who wrote it (group members)               |
| `type`         | `contact` or `group`                       |
| `text`         | Message body                               |
| `direction`    | `incoming` / `outgoing`                    |
| `status`       | `sent` / `delivered` / `read` / `sending`  |
| `item_id`      | Internal SimpleX ID                        |
| `timestamp`    | Message timestamp                          |
| `edited`       | Whether the message was edited             |
| `file`         | Attachment metadata (name, size, media URL)|

Other events: `simplex_targets_updated` (a chat was discovered or removed),
`simplex_activity_updated` (the activity counters changed) and `simplex_error`
(the CLI answered with a `chatCmdError`).

### Entities

Entities live on two kinds of devices:

- the **Simplex Chat** device — the integration itself
  (`sensor.simplex_chat_*`, `binary_sensor.simplex_chat_connection`);
- one device **per contact/group**, named after it
  (`sensor.alice_last_message`, `binary_sensor.alice_connected`, …).

| Entity | Description |
|--------|-------------|
| `binary_sensor.simplex_chat_connection` | WebSocket status (+ last CLI error as attributes) |
| `sensor.simplex_chat_last_message` | Last **received** message, with sender/timestamp attributes |
| `sensor.simplex_chat_known_contacts` | Number of chats known (configured + discovered) |
| `sensor.simplex_chat_configured_contacts` | Number of chats configured by hand |
| `sensor.simplex_chat_discovered_contacts` | Number of auto-discovered chats |
| `sensor.simplex_chat_unread_messages` | Total unread messages |
| `sensor.simplex_chat_last_error` | Last CLI error (diagnostic) |
| `sensor.simplex_chat_messages_today` | Messages received today (all chats) |
| `sensor.simplex_chat_messages_week` | Messages received over the last 7 days |
| `sensor.<contact>_last_message` | Last message of one contact/group |
| `sensor.<contact>_unread_messages` | Unread counter of one contact/group |
| `sensor.<contact>_messages_today` | Messages received today on one contact/group |
| `binary_sensor.<contact>_connected` | Connectivity of one contact/group |

> **Entity ids and the 2.0 upgrade** — the integration device used to be
> named *SimpleX Chat*, which Home Assistant slugifies to `simple_x_chat_*`.
> The ids documented above (`simplex_chat_*`) have always been the ones in
> the README and the dashboards, so before 2.0 the shipped dashboards could
> not find their entities. Version 2.0 renames the device and migrates the
> entity ids of existing installs automatically.

### Searching across every conversation

The conversation-list card's search box filters the list as you type.
Press **Enter** (or the 🔍 button) to search the *message text* of every
conversation at once — the CLI command behind it is
`/_get items count=<n> search=<text>`, which matches across all chats.

Results are grouped by conversation, with the matching snippets
highlighted; clicking a group opens that conversation. The same search is
available as the `simplex.search` service and the `simplex/search`
websocket command.

### Sending images

The chat view and the intercom card have a **picture button** (📷). The
upload endpoint accepts `image` as well as `audio` and `video`, and the
kind is inferred from the file extension when it is not stated.

Pictures are sent as SimpleX `image` content (not as generic file
attachments), so they are displayed inline by the SimpleX clients.

Accepted image extensions: `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`,
`.bmp`, `.heic`, `.heif`.

### Activity statistics

SimpleX exposes no counters, so the integration derives them from the
chat history: the counters are back-filled from the history at start-up
and then maintained incrementally.

The `daily` attribute of `sensor.simplex_chat_messages_week` holds the
per-day series the dashboards draw as a small bar chart. The
`simplex.activity_stats` service returns the same series plus a per-chat
breakdown.

### Assist / LLM

Two tools are registered automatically:

- `send_simplex_message` — *"Send a SimpleX message to Alice: I'll be home in 10 minutes"*
- `search_simplex_messages` — *"When did I tell Alice about the dinner?"*

---

## Dashboards & cards

Nine ready-to-use dashboards ship in [`dashboards/`](dashboards). Check the
[dependency table](#only-for-the-ready-made-dashboards) before copying one —
`simplex_mushroom_*.yaml` in particular needs [Mushroom][mushroom-url] and
[Auto Entities][auto-entities-url].

| File | Style |
|------|-------|
| `simplex_fr.yaml` / `simplex_en.yaml` | Status, actions, contact list |
| `simplex_mushroom_fr.yaml` / `_en.yaml` | Same, Mushroom style |
| `simplex_tablet_fr.yaml` | Wall tablet (intercom) |
| `simplex_auto_fr.yaml` / `simplex_auto_en.yaml` | **App-like**: conversation list + chat |
| `simplex_android_home_fr.yaml` | App-like, one generic chat view |
| `simplex_android_look_fr.yaml` | Conversation thread only |

### Installing the custom cards

The app-like dashboards need two Lovelace cards. Copy them to `/config/www/`
and register them under *Settings → Dashboards → Resources*:

```
/config/www/simplex-conversations-card/simplex-conversations-card.js
/config/www/simplex-chat-card/simplex-chat-card.js
```

Both as **JavaScript Module**. The wall-tablet dashboard additionally needs
`/config/www/simplex-intercom-card/simplex-intercom-card.js`.

### The dynamic mode — one view for every contact

The conversation list is filled by auto-discovery, so declaring a dashboard
view per contact would be pointless. The chat card therefore supports an
`auto` alias: it reads the alias from the URL.

```yaml
- type: custom:simplex-conversations-card
  navigate_prefix: /simplex-chat
  navigate_mode: hash        # default
- type: custom:simplex-chat-card
  alias: auto
```

Tapping a row navigates to `/simplex-chat#alice`. The fragment (`#`) carries
the alias and survives a page reload, so a single generic view serves every
contact. `navigate_mode: path` (`/simplex-chat/alice`) is available if you
prefer one path per contact.

An explicit `alias:` still works exactly as before — the dynamic mode is
opt-in per card.

### What the cards give you

**Conversation list** — search box, deterministic avatar colours, unread
highlight and badge, connection dot, relative timestamps, group icons, and a
counter of unread messages. It refreshes on new messages and on contact
discovery.

**Chat view** — day separators, group sender names, connection status in the
header, "mark as read" button, voice/video recording, picture sending, and
infinite scroll back through the history.

---

## Architecture

```
Home Assistant
    │
    ├── notify.* entities  ──┐
    ├── services           ──┼──► SimplexWsClient ──► ws://…:5225 ──► simplex-chat CLI
    ├── LLM tool           ──┘                              │
    │                                                       │
    └── events + sensors  ◄─────────────────────────────────┘
```

The WebSocket client handles automatic reconnection, RPC response correlation (`corrId`), event dispatch, and redaction of sensitive links in logs.

The **target registry** (`targets.py`) merges the manually configured chats
and the auto-discovered ones into a single view, so every consumer —
notify entities, sensors, the LLM tool, the dashboard cards — sees the same
list. Discovery is runtime-only: it never rewrites the config entry.

---

## Troubleshooting

### The dashboard shows "Custom element: mushroom-…"

Mushroom is not installed, or the resource was not registered. Install it via
HACS, then add `/local/mushroom.js` as a **JavaScript Module** in
*Settings → Dashboards → Resources* and reload the browser cache.

### The conversations card is empty

The app-like dashboards need the three SimpleX cards in `/config/www/`
(see [Installing the custom cards](#installing-the-custom-cards)) **and** the
`simplex-conversations-card` resource registered. If the list stays empty,
check that auto-discovery worked — `sensor.simplex_chat_discovered_contacts`
must be greater than 0.

### No message arrives

Enable debug logging:

```yaml
logger:
  default: info
  logs:
    custom_components.simplex: debug
```

Then check:

1. Is `simplex-chat -p 5225` running?
2. Is `binary_sensor.simplex_chat_connection` `on`?
3. Any `chatCmdError` entries in the logs? (`sensor.simplex_chat_last_error`)
4. Is the invitation link still valid?
5. A contact is missing? Call `simplex.refresh_contacts`. The integration also re-reads the CLI's contacts and groups after every reconnection, and logs a warning (`auto-discovery incomplete`) if a listing fails.

### The unread counters stay at zero

The bridge marks messages as read on arrival. Set `SIMPLEX_MARK_READ=false`
in the bridge's environment — see [DOCKER.md](DOCKER.md).

---

## Roadmap

- [x] Long-term user address
- [x] File / image sending
- [x] Auto-discovery of contacts and groups
- [x] Per-contact sensors and binary sensors
- [x] Lovelace cards
- [x] Chat / message search across conversations
- [x] Activity statistics
- [ ] Multi-profile support

---

## Tests

The repository ships a dependency-free test suite that replays **real**
SimpleX Chat CLI v7.1.4.0 frames through the integration's mapping:

```bash
python3 -m unittest discover -s tests -v
```

---

## Credits

- [SimpleX Chat][simplex] — the messenger itself, by [SimpleX Chat Ltd][simplex-ltd]
- [Mushroom][mushroom-url] — the Lovelace cards used by the Mushroom dashboards
- [Auto Entities][auto-entities-url] — used by the dashboards to list the entities dynamically
- [simplex-bridge][bridge-url] — the reference WebSocket daemon

---

## License

MIT

SimpleX Chat is a project by [SimpleX Chat Ltd][simplex-ltd]. This integration is an independent community project and is not officially affiliated.

<!-- Badges -->

[hacs-url]: https://github.com/hacs/integration
[hacs-badge]: https://img.shields.io/badge/hacs-default-orange.svg?style=flat-square
[release-badge]: https://img.shields.io/github/v/release/MX10-AC2N/SimpleX-Chat_HA?style=flat-square
[downloads-badge]: https://img.shields.io/github/downloads/MX10-AC2N/SimpleX-Chat_HA/total?style=flat-square

<!-- References -->

[simplex]: https://simplex.chat/
[simplex-ltd]: https://simplex.chat/
[mushroom-url]: https://github.com/piitaya/lovelace-mushroom
[auto-entities-url]: https://github.com/thomasloven/lovelace-auto-entities
[bridge-url]: https://github.com/MX10-AC2N/simplex-bridge
