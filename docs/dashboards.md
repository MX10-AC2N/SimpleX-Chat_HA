# Dashboards & cards

Nine ready-to-use dashboards ship in [`dashboards/`](../dashboards). They are
optional — the integration works on its own — but they need two community
Lovelace cards, which you must install first.

---

## Dependencies

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

---

## The dashboards

| File | Style |
|------|-------|
| `simplex_fr.yaml` / `simplex_en.yaml` | Status, actions, contact list |
| `simplex_mushroom_fr.yaml` / `_en.yaml` | Same, Mushroom style |
| `simplex_tablet_fr.yaml` | Wall tablet (intercom) |
| `simplex_auto_fr.yaml` / `simplex_auto_en.yaml` | **App-like**: conversation list + chat |
| `simplex_android_home_fr.yaml` | App-like, one generic chat view |
| `simplex_android_look_fr.yaml` | Conversation thread only |

Import one with *Settings → Dashboards → Add dashboard → Import from file*,
or copy the YAML into a view of your own.

---

## Installing the custom cards

The app-like dashboards need two Lovelace cards. Copy them to `/config/www/`
and register them under *Settings → Dashboards → Resources*:

```
/config/www/simplex-conversations-card/simplex-conversations-card.js
/config/www/simplex-chat-card/simplex-chat-card.js
```

Both as **JavaScript Module**. The wall-tablet dashboard additionally needs
`/config/www/simplex-intercom-card/simplex-intercom-card.js`.

---

## The dynamic mode — one view for every contact

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

---

## What the cards give you

**Conversation list** — search box, deterministic avatar colours, unread
highlight and badge, connection dot, relative timestamps, group icons, and a
counter of unread messages. It refreshes on new messages and on contact
discovery.

**Chat view** — day separators, group sender names, connection status in the
header, "mark as read" button, voice/video recording, picture sending, and
infinite scroll back through the history.

**Intercom (wall tablet)** — a big recipient picker, a picture button and a
record button, designed to be tapped by someone standing in front of the
screen.

---

## Next steps

- [Sending messages](usage.md)
- [Something not working?](troubleshooting.md)

<!-- References -->

[mushroom-url]: https://github.com/piitaya/lovelace-mushroom
[auto-entities-url]: https://github.com/thomasloven/lovelace-auto-entities
