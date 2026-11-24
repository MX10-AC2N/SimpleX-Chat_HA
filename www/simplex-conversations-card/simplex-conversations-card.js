/**
 * SimpleX Conversations Card
 * -----------------------------------------------------------------------
 * The "home screen" of a messaging app: one row per SimpleX contact/group
 * known to the bot, with an avatar, the last message preview, a timestamp
 * and an unread badge (when the CLI reports one — see note below). Tapping a
 * row navigates to the chat view.
 *
 * Since the integration auto-discovers the CLI's contacts and groups, this
 * card lists every conversation without any manual setup — the rows appear
 * as soon as the bot knows the contact.
 *
 * Navigation:
 *   navigate_prefix: /simplex-chat   +   navigate_mode: hash (default)
 *   → /simplex-chat#alice
 *   The alias travels in the URL hash, so ONE generic chat view serves
 *   every contact (see simplex-chat-card's "alias: auto" mode). The hash
 *   also survives a page reload, unlike the router's path.
 *
 *   navigate_mode: path  → /simplex-chat/alice
 *   Use it if your chat view lives on its own path per contact.
 *
 * Backend requirement: the `simplex` integration's HA websocket command
 * "simplex/conversations" (v2.2+, backed by `/chats all` since v2.3 so
 * households with more than 20 contacts all show up — see DOCKER.md).
 *
 * Note on unread badges: reads `chatStats.unreadCount`, confirmed present
 * on every chat preview (checked against the CLI's own Haskell source,
 * v7.1.4 — the version pinned in mx10-ac2n/simplex-bridge, see ws_api.py).
 * The `.get()` check is kept anyway as plain defensive coding; when it's
 * absent the row just shows no badge rather than a guessed/wrong count.
 *
 * Install: copy this file to /config/www/simplex-conversations-card/ and
 * add it as a Lovelace resource:
 *   URL:  /local/simplex-conversations-card/simplex-conversations-card.js
 *   Type: JavaScript Module
 *
 * Card config example:
 *   type: custom:simplex-conversations-card
 *   title: SimpleX
 *   navigate_prefix: /simplex-chat   # + alias, e.g. /simplex-chat#alice
 *   navigate_mode: hash              # "hash" (default) or "path"
 * -----------------------------------------------------------------------
 */

// Deterministic avatar colours: the same contact always gets the same hue.
const AVATAR_COLORS = [
  "#3fb37f", "#4a7fd4", "#c07a3f", "#a04a9e", "#c04a5e",
  "#3f9ec0", "#7a9e3f", "#b58b2e", "#5c6bc0", "#3fae8f",
];

class SimplexConversationsCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = null;
    this._conversations = [];
    this._unsubscribe = null;
    this._unsubscribeExtra = null;
    this._loaded = false;
    this._filter = "";
  }

  setConfig(config) {
    this._config = {
      title: config.title || "SimpleX",
      navigate_prefix: config.navigate_prefix || null,
      navigate_mode: config.navigate_mode || "hash",
      entry_id: config.entry_id || null,
      show_search: config.show_search !== false,
    };
    this._renderShell();
  }

  set hass(hass) {
    const first = this._hass === null;
    this._hass = hass;
    if (first) {
      this._load();
      this._subscribe();
    }
  }

  getCardSize() {
    return 3;
  }

  disconnectedCallback() {
    if (this._unsubscribe) {
      this._unsubscribe();
      this._unsubscribe = null;
    }
    if (this._unsubscribeExtra) {
      this._unsubscribeExtra();
      this._unsubscribeExtra = null;
    }
  }

  async _load() {
    try {
      const result = await this._hass.connection.sendMessagePromise({
        type: "simplex/conversations",
        ...(this._config.entry_id ? { entry_id: this._config.entry_id } : {}),
      });
      this._conversations = result.conversations || [];
      this._loaded = true;
      this._renderRows();
    } catch (err) {
      this._renderError(err.message || String(err));
    }
  }

  _subscribe() {
    // Any new message can change a row's preview/unread count — simplest
    // correct behaviour is to just refetch the (small) conversation list.
    // `simplex_targets_updated` covers the other case: a contact or group
    // that was just discovered must appear without a page reload.
    const reload = () => this._load();
    this.hass.connection
      .subscribeEvents(reload, "simplex_message_received")
      .then((unsub) => {
        this._unsubscribe = unsub;
      })
      .catch(() => {});
    this.hass.connection
      .subscribeEvents(reload, "simplex_targets_updated")
      .then((unsub) => {
        this._unsubscribeExtra = unsub;
      })
      .catch(() => {});
  }

  _renderShell() {
    const root = this.shadowRoot;
    root.innerHTML = `
      <style>
        ha-card {
          padding: 0; overflow: hidden;
          background: var(--simplex-bg, #0b141a);
        }
        .header {
          padding: 14px 16px 8px 16px; font-weight: 600; font-size: 1.1em;
          color: #fff; display: flex; align-items: center; justify-content: space-between;
        }
        .header .count { font-size: 0.72em; font-weight: 400; opacity: 0.6; }
        .search { padding: 0 12px 8px 12px; }
        .search input {
          width: 100%; box-sizing: border-box;
          padding: 8px 12px; border-radius: 18px; border: none;
          background: rgba(255,255,255,0.08); color: #eef3f5; font-size: 0.9em;
        }
        .search input::placeholder { color: #7d939a; }
        .rows { display: flex; flex-direction: column; }
        .row {
          display: flex; align-items: center; gap: 12px;
          padding: 10px 16px; cursor: pointer;
          border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        .row:hover { background: rgba(255,255,255,0.04); }
        .row.unread { background: rgba(63,179,127,0.10); }
        .row.unread .name { font-weight: 700; }
        .avatar {
          width: 44px; height: 44px; border-radius: 50%; flex: 0 0 auto;
          background: #2f9e6f;
          display: flex; align-items: center; justify-content: center;
          color: #fff; font-weight: 600;
          position: relative;
        }
        .avatar.group { font-size: 1.2em; }
        .avatar .dot {
          position: absolute; right: -1px; bottom: -1px;
          width: 11px; height: 11px; border-radius: 50%;
          background: #7d939a; border: 2px solid var(--simplex-bg, #0b141a);
        }
        .avatar .dot.on { background: #3fb37f; }
        .body { flex: 1 1 auto; min-width: 0; }
        .name-row { display: flex; justify-content: space-between; gap: 8px; }
        .name { color: #eef3f5; font-weight: 600; font-size: 0.97em; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .time { color: #7d939a; font-size: 0.75em; flex: 0 0 auto; }
        .preview-row { display: flex; justify-content: space-between; gap: 8px; margin-top: 2px; }
        .preview {
          color: #9fb3ba; font-size: 0.86em; white-space: nowrap;
          overflow: hidden; text-overflow: ellipsis;
        }
        .badge {
          background: #2f9e6f; color: #fff; border-radius: 10px;
          min-width: 18px; height: 18px; padding: 0 5px;
          font-size: 0.72em; display: flex; align-items: center; justify-content: center;
          flex: 0 0 auto;
        }
        .empty, .error { color: #9fb3ba; text-align: center; padding: 24px; font-size: 0.9em; }
        .error { color: #e08a8a; }
      </style>
      <ha-card>
        <div class="header">
          <span>${this._escape(this._config.title)}</span>
          <span class="count" id="count"></span>
        </div>
        ${this._config.show_search
          ? `<div class="search"><input id="search" type="text" placeholder="Rechercher…" /></div>`
          : ""}
        <div class="rows" id="rows"><div class="empty">Chargement…</div></div>
      </ha-card>
    `;

    const search = root.getElementById("search");
    if (search) {
      search.addEventListener("input", (e) => {
        this._filter = (e.target.value || "").trim().toLowerCase();
        this._renderRows();
      });
    }
  }

  _renderError(message) {
    const el = this.shadowRoot.getElementById("rows");
    if (el) el.innerHTML = `<div class="error">${this._escape(message)}</div>`;
  }

  _visibleRows() {
    // Most recent conversation first.
    const rows = this._conversations.slice().sort((a, b) => {
      const ta = this._timestamp(a);
      const tb = this._timestamp(b);
      if (tb !== ta) return tb - ta;
      return String(a.name || "").localeCompare(String(b.name || ""));
    });
    if (!this._filter) return rows;
    return rows.filter((c) =>
      `${c.name || ""} ${c.alias || ""} ${c.chat_ref || ""}`
        .toLowerCase()
        .includes(this._filter)
    );
  }

  _renderRows() {
    const el = this.shadowRoot.getElementById("rows");
    if (!el) return;
    const rows = this._visibleRows();

    const countEl = this.shadowRoot.getElementById("count");
    if (countEl) {
      const unread = this._conversations.reduce(
        (sum, c) => sum + (c.unread_count > 0 ? c.unread_count : 0),
        0
      );
      countEl.textContent = unread
        ? `${this._conversations.length} · ${unread} non-lus`
        : `${this._conversations.length}`;
    }

    if (!rows.length) {
      el.innerHTML = this._loaded
        ? (this._filter
            ? '<div class="empty">Aucun contact ne correspond à la recherche.</div>'
            : '<div class="empty">Aucun contact pour l’instant. Les contacts et groupes du bot SimpleX apparaissent ici automatiquement.</div>')
        : '<div class="empty">Chargement…</div>';
      return;
    }

    el.innerHTML = rows
      .map((c) => {
        const last = c.last_message;
        let preview = "";
        if (last) {
          if (last.file) {
            preview = `📎 ${this._escape(last.file.name || "Fichier")}`;
          } else {
            preview = this._escape(last.text || "");
          }
          // Outgoing messages are prefixed so a row is never ambiguous.
          if (last.direction === "outgoing") preview = `↩ ${preview}`;
        }
        const time = last ? this._formatTime(last.timestamp) : "";
        const unread = c.unread_count && c.unread_count > 0;
        const badge = unread
          ? `<div class="badge">${c.unread_count > 99 ? "99+" : c.unread_count}</div>`
          : "";
        const dot = `<span class="dot${c.connected ? " on" : ""}"></span>`;
        const face = c.type === "group" ? "👥" : this._initial(c.name);
        const avatar = `<div class="avatar${c.type === "group" ? " group" : ""}" style="background:${this._avatarColor(c.alias)}">${face}${dot}</div>`;
        return `
          <div class="row${unread ? " unread" : ""}" data-alias="${this._escape(c.alias)}">
            ${avatar}
            <div class="body">
              <div class="name-row">
                <span class="name">${this._escape(c.name)}</span>
                <span class="time">${time}</span>
              </div>
              <div class="preview-row">
                <span class="preview">${preview}</span>
                ${badge}
              </div>
            </div>
          </div>`;
      })
      .join("");

    el.querySelectorAll(".row").forEach((rowEl) => {
      rowEl.addEventListener("click", () => this._onRowClick(rowEl.dataset.alias));
    });
  }

  _timestamp(conversation) {
    // The CLI returns ISO-8601 strings; Date.getTime() makes them sortable.
    const ts = conversation && conversation.last_message && conversation.last_message.timestamp;
    if (!ts) return 0;
    const value = new Date(ts).getTime();
    return Number.isNaN(value) ? 0 : value;
  }

  _avatarColor(alias) {
    const key = String(alias || "");
    let hash = 0;
    for (let i = 0; i < key.length; i++) {
      hash = (hash * 31 + key.charCodeAt(i)) >>> 0;
    }
    return AVATAR_COLORS[hash % AVATAR_COLORS.length];
  }

  _onRowClick(alias) {
    if (!this._config.navigate_prefix || !alias) return;
    // Belt-and-braces: Home Assistant owns the router and may normalise the
    // URL (dropping the hash). The sessionStorage copy is the fallback the
    // chat card reads when the hash is gone.
    try {
      window.sessionStorage.setItem("simplex_chat_alias", alias);
    } catch (e) {
      /* private mode: the hash alone will do */
    }
    const base = this._config.navigate_prefix.replace(/\/+$/, "");
    const path =
      this._config.navigate_mode === "path"
        ? `${base}/${alias}`
        : `${base}#${encodeURIComponent(alias)}`;
    this.dispatchEvent(
      new CustomEvent("location-changed", { bubbles: true, composed: true, detail: { replace: false } })
    );
    window.history.pushState(null, "", path);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }

  _formatTime(ts) {
    if (!ts) return "";
    const d = new Date(ts);
    if (Number.isNaN(d.getTime())) return "";
    const now = new Date();
    const sameDay = d.toDateString() === now.toDateString();
    if (sameDay) {
      return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }
    const yesterday = new Date();
    yesterday.setDate(now.getDate() - 1);
    if (d.toDateString() === yesterday.toDateString()) return "Hier";
    return d.toLocaleDateString([], { day: "2-digit", month: "2-digit" });
  }

  _escape(str) {
    const d = document.createElement("div");
    d.textContent = str || "";
    return d.innerHTML;
  }

  _initial(name) {
    return this._escape((name || "?").trim().charAt(0).toUpperCase());
  }
}

customElements.define("simplex-conversations-card", SimplexConversationsCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "simplex-conversations-card",
  name: "SimpleX Conversations",
  description: "Écran d'accueil façon appli SimpleX : liste des contacts avec aperçu du dernier message et badge non-lus.",
});
