# SimpleX Chat for Home Assistant

Complete HACS integration to send and receive messages via [SimpleX Chat](https://simplex.chat/) from Home Assistant.

SimpleX is a messenger that is private by design (no user identifiers, end-to-end encryption, minimal metadata). This integration lets you use SimpleX as a secure notification and messaging channel for your smart home.

> 🇫🇷 **Version française** : [README_fr.md](README_fr.md)

---

## Features

- **Native notifications** — one `notify.*` entity per contact or group
- **Incoming messages** — `simplex_message_received` event + sensor
- **Connection status** — WebSocket `binary_sensor`
- **Services** — send message, create invite, accept link, list contacts
- **LLM / Assist tool** — `send_simplex_message` for voice and AI agents
- **Automatic reconnection** with exponential backoff
- **Translations** EN / FR
- Ready for **HACS** and the Home Assistant **Marketplace**

---

## Requirements

1. **SimpleX Chat CLI** in WebSocket mode:

```bash
simplex-chat -p 5225
```

Minimal Docker example:

```bash
docker run -d --name simplex-ws \
  -p 5225:5225 \
  -v simplex-data:/home/user/.local/share/simplex \
  --restart unless-stopped \
  <simplex-ws-image>
```

2. Home Assistant **2025.8+** (2026.x recommended).

---

## Installation

### Via HACS (recommended)

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

---

## Configuring contacts

1. **Settings → Devices & services → SimpleX Chat → Configure**
2. Choose **Add a contact / group**
3. Enter a friendly alias (e.g. `Alice`, `Family`)
4. Paste a SimpleX invitation link (1:1 or group)
5. A `notify.simplex_alice` entity (or similar) is created automatically

You can also remove contacts or list them from the same menu.

---

## Usage

### Notifications

```yaml
action: notify.send_message
data:
  message: "Dinner is ready!"
  title: "Home"
target:
  entity_id: notify.simplex_alice
```

Multiple recipients:

```yaml
target:
  entity_id:
    - notify.simplex_alice
    - notify.simplex_family
```

### Dedicated service

```yaml
action: simplex.send_message
data:
  alias: Alice
  message: "Front door opened"
  title: "Security"
```

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

| Key         | Description                      |
|-------------|----------------------------------|
| `alias`     | Configured alias (if matched)    |
| `chat_ref`  | `@123` or `#456`                 |
| `text`      | Message body                     |
| `direction` | `incoming` / `outgoing`          |
| `item_id`   | Internal SimpleX ID              |

### Sensors

| Entity | Description |
|--------|-------------|
| `binary_sensor.simplex_chat_connection` | WebSocket status |
| `sensor.simplex_chat_last_message` | Last received message |
| `sensor.simplex_chat_configured_contacts` | Number of contacts |

### Assist / LLM

The `send_simplex_message` tool is registered automatically. Example:

> “Send a SimpleX message to Alice: I’ll be home in 10 minutes”

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

---

## Troubleshooting

Enable debug logging:

```yaml
logger:
  default: info
  logs:
    custom_components.simplex: debug
```

Checklist:

1. Is `simplex-chat -p 5225` running?
2. Is `binary_sensor.simplex_chat_connection` `on`?
3. Any `chatCmdError` entries in the logs?
4. Is the invitation link still valid?

---

## Roadmap

- [ ] Long-term user address
- [ ] File / image sending
- [ ] Multi-profile support
- [ ] Lovelace card
- [ ] Auto-discovery of contacts already known to the CLI

---

## License

MIT

SimpleX Chat is a project by [SimpleX Chat Ltd](https://simplex.chat). This integration is an independent community project and is not officially affiliated.
