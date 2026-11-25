# Installation

## Requirements

### Required

1. **SimpleX Chat CLI** in WebSocket mode:

   ```bash
   simplex-chat -p 5225
   ```

2. Home Assistant **2025.8+** (2026.x recommended).

When Home Assistant runs in Docker, do **not** use `127.0.0.1` from inside
the HA container unless both containers share the host network namespace.
See the dedicated guide: **[DOCKER.md](../DOCKER.md)**.

---

## Via HACS (recommended)

1. HACS → Integrations → ⋮ → **Custom repositories**
2. URL: `https://github.com/MX10-AC2N/SimpleX-Chat_HA`
3. Category: **Integration**
4. Download → Restart Home Assistant
5. **Settings → Devices & services → Add integration → SimpleX Chat**
6. Enter the WebSocket URL (default: `ws://127.0.0.1:5225`)

Or open the repository directly in HACS:

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=MX10-AC2N&repository=SimpleX-Chat_HA)

---

## Manual installation

```bash
cd /config/custom_components
# copy the simplex/ folder from this repository
```

Restart Home Assistant, then add the integration from the UI.

---

## Docker

If Home Assistant runs in Docker, you **must** run a SimpleX Chat WebSocket
daemon alongside it.

→ Full guide: **[DOCKER.md](../DOCKER.md)** (compose examples, networking,
troubleshooting).

The reference daemon is **[MX10-AC2N/simplex-bridge][bridge-url]**, whose
WebSocket contract is validated by a dedicated test suite (T01–T13).

---

## Bridge configuration

Two environment variables on the bridge change how the integration behaves:

| Variable | Default | Effect |
|----------|---------|--------|
| `SIMPLEX_AUTO_ACCEPT` | `false` | Accept contact requests automatically — **required** for auto-discovery |
| `SIMPLEX_MARK_READ` | `false` | When `true`, the CLI marks every message as read on arrival and the unread counters stay at zero |

Both default to the value that makes the integration behave as documented.
See [DOCKER.md](../DOCKER.md) for the full compose examples.

---

## Next steps

- [Configure your contacts](configuration.md)
- [Send your first message](usage.md)
- [Install a dashboard](dashboards.md)

<!-- References -->

[bridge-url]: https://github.com/MX10-AC2N/simplex-bridge
