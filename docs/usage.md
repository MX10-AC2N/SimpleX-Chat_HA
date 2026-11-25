# Usage

## Notifications

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

---

## Services

### Send a message

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

### Send a file or an image

```yaml
action: simplex.send_file
data:
  alias: Alice
  file_path: /config/simplex_outbox/clip.ogg
  message: "Doorbell recording"   # optional caption
```

The path must be readable by the `simplex-chat` process — use a volume
shared with the bridge container (see [DOCKER.md](../DOCKER.md)).

### Search across every conversation

```yaml
action: simplex.search
data:
  query: "dinner"
  limit: 50
```

### Activity statistics

```yaml
action: simplex.activity_stats
data:
  days: 30
```

Returns the daily series and the per-chat breakdown (count over the window,
all-time total, unread count).

### Create an invitation

```yaml
action: simplex.create_invite
```

The response contains `invite_link`.

### Accept an invitation

```yaml
action: simplex.accept_invite
data:
  invite_link: "https://simplex.chat/invitation#..."
  alias: Bob
```

### Discover / refresh

```yaml
action: simplex.refresh_contacts
```

Forces a re-read of the CLI's contact and group lists. The integration also
re-reads them after every reconnection.

### Mark as read

```yaml
action: simplex.mark_read
data:
  alias: Alice
  item_ids: [17, 18]
```

---

## Incoming events

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

| Key            | Description                                 |
|----------------|---------------------------------------------|
| `alias`        | Alias of the chat (configured or derived)   |
| `chat_ref`     | `@123` or `#456`                            |
| `display_name` | Display name of the contact / group         |
| `sender`       | Who wrote it (group members)                |
| `type`         | `contact` or `group`                        |
| `text`         | Message body                                |
| `direction`    | `incoming` / `outgoing`                     |
| `status`       | `sent` / `delivered` / `read` / `sending`   |
| `item_id`      | Internal SimpleX ID                         |
| `timestamp`    | Message timestamp                           |
| `edited`       | Whether the message was edited              |
| `file`         | Attachment metadata (name, size, media URL) |

Other events:

| Event | Fired when |
|-------|-----------|
| `simplex_targets_updated` | A chat was discovered or removed |
| `simplex_activity_updated` | The activity counters changed |
| `simplex_error` | The CLI answered with a `chatCmdError` |

---

## Entities

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

---

## Searching across every conversation

The conversation-list card's search box filters the list as you type.
Press **Enter** (or the 🔍 button) to search the *message text* of every
conversation at once — the CLI command behind it is
`/_get items count=<n> search=<text>`, which matches across all chats.

Results are grouped by conversation, with the matching snippets
highlighted; clicking a group opens that conversation. The same search is
available as the `simplex.search` service and the `simplex/search`
websocket command.

---

## Sending images

The chat view and the intercom card have a **picture button** (📷). The
upload endpoint accepts `image` as well as `audio` and `video`, and the
kind is inferred from the file extension when it is not stated.

Pictures are sent as SimpleX `image` content (not as generic file
attachments), so they are displayed inline by the SimpleX clients.

Accepted image extensions: `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`,
`.bmp`, `.heic`, `.heif`.

---

## Activity statistics

SimpleX exposes no counters, so the integration derives them from the
chat history: the counters are back-filled from the history at start-up
and then maintained incrementally.

The `daily` attribute of `sensor.simplex_chat_messages_week` holds the
per-day series the dashboards draw as a small bar chart. The
`simplex.activity_stats` service returns the same series plus a per-chat
breakdown.

---

## Assist / LLM

Two tools are registered automatically:

- `send_simplex_message` — *"Send a SimpleX message to Alice: I'll be home in 10 minutes"*
- `search_simplex_messages` — *"When did I tell Alice about the dinner?"*

---

## Next steps

- [Install a dashboard](dashboards.md)
- [Something not working?](troubleshooting.md)
