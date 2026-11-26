# 💬 SimpleX Chat for Home Assistant

[![hacs][hacs-badge]][hacs-url]
[![release][release-badge]][release-url]
![downloads][downloads-badge]

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=MX10-AC2N&repository=SimpleX-Chat_HA)

> 🇫🇷 **Version française** : [README_fr.md](README_fr.md)

SimpleX Chat is a messenger with **no user identifiers**, end-to-end
encryption and minimal metadata. This integration brings it into Home
Assistant as a first-class citizen: a secure notification channel for your
home, a messaging front-end for a wall tablet, and a target for voice
assistants and AI agents.

---

## What you get

**Messaging**
- 🔎 Auto-discovery — contacts and groups appear on their own, no invitation link to paste for each of them
- 🔔 One `notify.*` entity per contact or group
- 💬 Incoming messages as events and sensors
- ⚡ Live connection tracking — a contact accepted while HA runs shows up immediately

**Content**
- 🖼️ Images, audio and video, sent as real SimpleX content and displayed inline
- 🔍 Search across every conversation, from the card or from a service
- 📊 Activity statistics — messages per day and per contact

**Home Assistant**
- 📇 One device per contact: last message, unread counter, connectivity
- 🧩 10 services: send, search, statistics, invitations, refresh, mark as read…
- 🤖 Two Assist/LLM tools: `send_simplex_message` and `search_simplex_messages`
- 📦 11 ready-to-use dashboards, from a status wall to a Glass messenger
- 🌍 English and French

---

## Getting started

```bash
simplex-chat -p 5225
```

Then add the integration:

**Settings → Devices & services → Add integration → SimpleX Chat**,
and enter the WebSocket URL (`ws://127.0.0.1:5225` by default).

Your contacts are discovered automatically — you should see a
`notify.simplex_chat_*` entity for each of them a few seconds later.

Running Home Assistant in Docker? The CLI runs in a separate container:
→ **[DOCKER.md](DOCKER.md)**.

---

## Requirements

- **SimpleX Chat CLI** in WebSocket mode (`simplex-chat -p 5225`)
- Home Assistant **2025.8+**

The three SimpleX Lovelace cards (with a visual editor) and the dashboards ship with the integration — install a dashboard in one click from *Configure → Install a dashboard*.

---

## Dashboards

| Dashboard | [Mushroom][mushroom-url] | [Auto Entities][auto-entities-url] | SimpleX cards |
|-----------|--------------------------|-----------------------------------|---------------|
| `simplex_fr.yaml` / `simplex_en.yaml` | – | ✅ required | – |
| `simplex_mushroom_fr.yaml` / `_en.yaml` | ✅ **required** | ✅ required | – |
| `simplex_auto_fr.yaml` / `_en.yaml` | – | – | ✅ required |
| `simplex_tablet_fr.yaml` | – | – | ✅ required (intercom) |
| `simplex_android_home_fr.yaml` | – | – | ✅ required |
| `simplex_android_look_fr.yaml` | – | – | ✅ required |

> ⚠️ **`simplex_mushroom_*.yaml` does not render at all without Mushroom.**
> The cards show up as "Custom element: mushroom-…" with an error in the
> browser console.

Install with HACS → *Integrations* → **Mushroom** → download, then add
`/local/mushroom.js` as a **JavaScript Module** in *Settings → Dashboards →
Resources*.

Full details: **[docs/dashboards.md](docs/dashboards.md)**.

---

## Documentation

| | |
|---|---|
| 📦 **[Installation](docs/installation.md)** | HACS, manual, Docker, bridge configuration |
| ⚙️ **[Configuration](docs/configuration.md)** | Auto-discovery, aliases, manual contacts |
| 💬 **[Usage](docs/usage.md)** | Services, events, entities, search, images, statistics, LLM |
| 🗂 **[Dashboards & cards](docs/dashboards.md)** | The 11 dashboards, the Glass Messenger, dependencies, dynamic mode |
| 🩺 **[Troubleshooting](docs/troubleshooting.md)** | By symptom: blank cards, no message, counters at zero… |
| 🛠 **[Development](docs/development.md)** | Architecture, modules, tests, roadmap |

---

## Credits

- [SimpleX Chat](https://simplex.chat/) — the messenger itself
- [Mushroom](https://github.com/piitaya/lovelace-mushroom) and [Auto Entities](https://github.com/thomasloven/lovelace-auto-entities) — the Lovelace cards the dashboards build on
- [simplex-bridge](https://github.com/MX10-AC2N/simplex-bridge) — the reference WebSocket daemon

## License

MIT — SimpleX Chat is a project by [SimpleX Chat Ltd](https://simplex.chat/).
This integration is an independent community project and is not officially
affiliated.

<!-- Badges -->

[hacs-url]: https://github.com/hacs/integration
[hacs-badge]: https://img.shields.io/badge/hacs-default-orange.svg?style=flat-square
[release-badge]: https://img.shields.io/github/v/release/MX10-AC2N/SimpleX-Chat_HA?style=flat-square
[downloads-badge]: https://img.shields.io/github/downloads/MX10-AC2N/SimpleX-Chat_HA/total?style=flat-square

<!-- References -->

[mushroom-url]: https://github.com/piitaya/lovelace-mushroom
[auto-entities-url]: https://github.com/thomasloven/lovelace-auto-entities
