# Development

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

| Module | Role |
|--------|------|
| `websocket_client.py` | WebSocket transport, RPC correlation (`corrId`), event dispatch, reconnection with exponential backoff, redaction of sensitive links in logs |
| `mapping.py` | Pure mapping between the CLI frames and the integration's own dicts — no I/O, so it is directly unit-testable |
| `targets.py` | The runtime registry: manual contacts + auto-discovered ones, merged into a single view |
| `stats.py` | Activity counters derived from the chat history |
| `entity_base.py` | Shared entity helpers (device naming, state) |
| `ws_api.py` | The websocket commands the dashboard cards call |
| `http.py` | The upload endpoint used by the wall tablet |
| `llm_api.py` | The Assist / LLM tools |

Discovery is runtime-only: it never rewrites the config entry, so no reload
is triggered and nothing is written to the storage.

---

## Tests

The repository ships a dependency-free test suite that replays **real**
SimpleX Chat CLI v7.1.4.0 frames through the integration's mapping:

```bash
python3 -m unittest discover -s tests -v
```

No `homeassistant`, `aiohttp`, `voluptuous` or `yaml` needed — the stubs live
in `tests/ha_stubs.py`, so the suite runs anywhere Python 3.9+ does.

| File | Covers |
|------|--------|
| `tests/test_simplex.py` | Mapping, targets, stats, upload kinds, services, websocket client |
| `tests/test_lifecycle.py` | Connection lifecycle, `accept_invite_link`, auto-discovery edge cases |
| `tests/data/cli_v7_replay_frames.json` | Real CLI frames captured from v7.1.4.0 |

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

## Credits

- [SimpleX Chat](https://simplex.chat/) — the messenger itself, by
  [SimpleX Chat Ltd](https://simplex.chat/)
- [Mushroom](https://github.com/piitaya/lovelace-mushroom) — the Lovelace
  cards used by the Mushroom dashboards
- [Auto Entities](https://github.com/thomasloven/lovelace-auto-entities) —
  used by the dashboards to list the entities dynamically
- [simplex-bridge](https://github.com/MX10-AC2N/simplex-bridge) — the
  reference WebSocket daemon
