# Dashboards & cards

Eleven ready-to-use dashboards ship **inside the integration**
([`custom_components/simplex/dashboards/`](../custom_components/simplex/dashboards)).
They are optional — the integration works on its own. The SimpleX cards are
installed for you; Mushroom / Auto Entities (see below) are only needed by some.

## One-click install

*Settings → Devices & services → SimpleX Chat → Configure → **Install a dashboard***,
or:

```yaml
action: simplex.install_dashboard
data:
  dashboard: simplex_auto_fr   # any file name from the list below, without .yaml
  url_path: simplex-auto-fr    # optional, must contain a hyphen
  overwrite: false             # true = replace an existing UI-mode dashboard
```

Administrators only. It creates a sidebar dashboard, rewrites the chat navigation
to the new URL, never writes to YAML-mode dashboards and never overwrites without
`overwrite: true`.

---

## Dependencies

| Dashboard | [Mushroom][mushroom-url] | [Auto Entities][auto-entities-url] | SimpleX cards |
|-----------|--------------------------|-----------------------------------|---------------|
| `simplex_fr.yaml` / `simplex_en.yaml` | – | ✅ required | – |
| `simplex_mushroom_fr.yaml` / `simplex_mushroom_en.yaml` | ✅ **required** | ✅ required | – |
| `simplex_auto_fr.yaml` / `simplex_auto_en.yaml` | – | – | ✅ required |
| `simplex_messenger_fr.yaml` / `simplex_messenger_en.yaml` | – | – | ✅ required (installed with the integration) |
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
| `simplex_messenger_fr.yaml` / `simplex_messenger_en.yaml` | **Glass Messenger**: list + chat in one responsive view (see below) |
| `simplex_auto_fr.yaml` / `simplex_auto_en.yaml` | **App-like**: conversation list + chat |
| `simplex_android_home_fr.yaml` | App-like, one generic chat view |
| `simplex_android_look_fr.yaml` | Conversation thread only |

Import one with *Settings → Dashboards → Add dashboard → Import from file*,
or copy the YAML into a view of your own.

---

## The custom cards (installed automatically)

The integration serves the three cards and loads them in the frontend: nothing to
copy to `/config/www`, no Lovelace resource to declare. Hard-refresh the browser
(Ctrl+F5) after an update. Resources you added by hand as `/local/...` can be
removed; keeping them is harmless.

### Visual editor — no YAML needed

Add a card → search **SimpleX** → fill in the form: contact alias, title, history
size, SimpleX instance (picker), connection sensor (picker), navigation mode,
recipients… The editor follows your language (English / French).

---

## SimpleX Messenger (Glass)

`custom:simplex-messenger-card` is one card that hosts the conversation list and
the chat. Desktop / tablet: list on the left, conversation on the right. Phone:
the list, then a full-screen conversation with a back button (the browser's Back
button works too). It reuses the two cards above, so voice, video, pictures,
files and read receipts behave exactly as before.

```yaml
views:
  - title: Messenger
    path: messenger
    type: panel
    cards:
      - type: custom:simplex-messenger-card
        glass_intensity: balanced   # off | subtle | balanced | strong
```

| Option | Default | |
|--------|---------|--|
| `glass_intensity` | `balanced` | `off` disables the blur: use it on wall tablets and older phones |
| `show_branding` | `true` | SimpleX header bar |
| `title` | *Conversations* | Title of the list |
| `show_search` | `true` | Search box of the list |
| `history_limit`, `auto_mark_read`, `entry_id`, `connection_entity` | as the chat card | Forwarded to the cards |
| `navigate_prefix` | *auto* | Path of **the view hosting the card**. Detected from the URL; only set it if you know why |

> ⚠️ `navigate_prefix`, when set, must be the path of the view that contains the
> messenger (`/<dashboard>/messenger`). Pointing it elsewhere makes Home Assistant
> leave the view on every click. The shipped dashboards leave it out.

The easiest way in is *Configure → Install a dashboard → `simplex_messenger_fr`
(or `_en`)*. The card also has a visual editor.

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
