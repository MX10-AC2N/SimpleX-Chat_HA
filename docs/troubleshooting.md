# Troubleshooting

Enable debug logging first — it makes every other check easier:

```yaml
logger:
  default: info
  logs:
    custom_components.simplex: debug
```

---

## The dashboard shows "Custom element: mushroom-…"

Mushroom is not installed, or the resource was not registered. Install it via
HACS, then add `/local/mushroom.js` as a **JavaScript Module** in
*Settings → Dashboards → Resources* and reload the browser cache.

The same symptom on an `auto-entities` card means
[Auto Entities](https://github.com/thomasloven/lovelace-auto-entities) is
missing.

---

## The conversations card is empty

The three SimpleX cards are loaded by the integration itself. Hard-refresh the
browser (Ctrl+F5); if the card is still unknown, check the log for
`Could not register the SimpleX Lovelace cards` and that the *Frontend* integration is loaded.

If the list stays empty, check that auto-discovery worked —
`sensor.simplex_chat_discovered_contacts` must be greater than 0. If it is
zero, see *Auto-discovery finds nothing* below.

---

## No message arrives

1. Is `simplex-chat -p 5225` running?
2. Is `binary_sensor.simplex_chat_connection` `on`?
3. Any `chatCmdError` entries in the logs? (`sensor.simplex_chat_last_error`)
4. Is the invitation link still valid?
5. A contact is missing? Call `simplex.refresh_contacts`. The integration also re-reads the CLI's contacts and groups after every reconnection, and logs a warning (`auto-discovery incomplete`) if a listing fails.

---

## Auto-discovery finds nothing

Auto-discovery needs the bridge to accept contact requests automatically.
Set `SIMPLEX_AUTO_ACCEPT=true` in the bridge's environment and restart it —
see [DOCKER.md](../DOCKER.md).

---

## The unread counters stay at zero

The bridge marks messages as read on arrival. Set `SIMPLEX_MARK_READ=false`
in the bridge's environment — see [DOCKER.md](../DOCKER.md).

---

## The entities are not found in the dashboard

The integration device was renamed from *SimpleX Chat* to *Simplex Chat* in
version 2.0, which changed the entity ids from `simple_x_chat_*` to
`simplex_chat_*`. Existing installs are migrated automatically — but a
dashboard that hard-codes the old ids has to be updated.

See [Entity ids and the 2.0 upgrade](usage.md#entities).

---

## The WebSocket keeps dropping

The client reconnects automatically with an exponential backoff. If it never
stays up, check that the URL matches what the bridge listens on
(`ws://127.0.0.1:5225` by default) and that the port is not already used by
another instance — see [DOCKER.md](../DOCKER.md) for the port-conflict
section.

---

## Still stuck?

Open an issue with:

- the output of the debug log,
- the value of `sensor.simplex_chat_last_error`,
- your Home Assistant version and the integration version
  (*Settings → Devices & services → SimpleX Chat*).
