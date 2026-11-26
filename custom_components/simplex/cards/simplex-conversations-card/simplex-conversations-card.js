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
 * Install: automatic — the SimpleX Chat integration serves this card and
 * loads it in the frontend; no Lovelace resource to add.
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
    this._subscribed = false;
    this._loadSeq = 0;
    this._reloadTimer = null;
    this._loaded = false;
    this._filter = "";
    this._mode = "list"; // "list" | "search"
    this._searchResults = null;
    this._searchCount = 0;
    this._searching = false;
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
    // The shell was rebuilt: repaint what is already in memory.
    if (this._loaded) this._renderRows();
  }

  set hass(hass) {
    const first = this._hass === null;
    this._hass = hass;
    if (first) {
      this._load();
      this._subscribe();
    }
  }

  // Visual editor (Edit card → no YAML). Provided by simplex-card-editor.js,
  // which the integration loads next to the cards.
  static getConfigElement() {
    return document.createElement("simplex-conversations-card-editor");
  }

  static getStubConfig() {
    return { title: "SimpleX" };
  }

  getGridOptions() {
    return { columns: 6, rows: 6, min_columns: 4, min_rows: 3 };
  }

  getCardSize() {
    return 3;
  }

  connectedCallback() {
    // Home Assistant detaches/re-attaches cards (view switch, edit mode);
    // `set hass` only subscribes once, so re-subscribe and catch up on what
    // was missed while detached.
    if (this._hass) {
      this._subscribe();
      this._load();
    }
  }

  disconnectedCallback() {
    this._subscribed = false;
    if (this._reloadTimer) {
      window.clearTimeout(this._reloadTimer);
      this._reloadTimer = null;
    }
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
    // A burst of messages fires several overlapping requests: only the latest
    // answer may be applied, otherwise a slow old reply overwrites a new one.
    const seq = ++this._loadSeq;
    try {
      const result = await this._hass.connection.sendMessagePromise({
        type: "simplex/conversations",
        ...(this._config.entry_id ? { entry_id: this._config.entry_id } : {}),
      });
      if (seq !== this._loadSeq) return;
      this._conversations = result.conversations || [];
      this._loaded = true;
      this._renderRows();
    } catch (err) {
      if (seq !== this._loadSeq) return;
      this._renderError(err.message || String(err));
    }
  }

  _subscribe() {
    if (this._subscribed || !this._hass) return;
    this._subscribed = true;
    // Any new message can change a row's preview/unread count — simplest
    // correct behaviour is to just refetch the (small) conversation list.
    // `simplex_targets_updated` covers the other case: a contact or group
    // that was just discovered must appear without a page reload.
    const reload = () => {
      if (this._reloadTimer) return; // coalesce bursts into one refetch
      this._reloadTimer = window.setTimeout(() => {
        this._reloadTimer = null;
        this._load();
      }, 250);
    };
    this._hass.connection
      .subscribeEvents(reload, "simplex_message_received")
      .then((unsub) => {
        if (!this._subscribed) return unsub(); // detached before it resolved
        this._unsubscribe = unsub;
      })
      .catch(() => {});
    this._hass.connection
      .subscribeEvents(reload, "simplex_targets_updated")
      .then((unsub) => {
        if (!this._subscribed) return unsub();
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
        .search { padding: 0 12px 8px 12px; display: flex; gap: 6px; }
        .search input {
          flex: 1 1 auto; min-width: 0; box-sizing: border-box;
          padding: 8px 12px; border-radius: 18px; border: none;
          background: rgba(255,255,255,0.08); color: #eef3f5; font-size: 0.9em;
        }
        .search input::placeholder { color: #7d939a; }
        .search button {
          flex: 0 0 auto; border: none; border-radius: 18px;
          padding: 0 12px; background: #2f9e6f; color: #fff; cursor: pointer;
          font-size: 0.85em;
        }
        .search button:disabled { background: #3b4c55; cursor: default; }
        .search-hint {
          padding: 0 16px 6px 16px; color: #7d939a; font-size: 0.72em;
        }
        .snippet {
          color: #9fb3ba; font-size: 0.86em; white-space: nowrap;
          overflow: hidden; text-overflow: ellipsis;
        }
        .snippet mark { background: rgba(63,179,127,0.35); color: #fff; border-radius: 3px; }
        .back-btn {
          background: none; border: none; color: #6fd3ff; cursor: pointer;
          font-size: 0.8em; padding: 0 0 6px 16px;
        }
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
          ? `<div class="search">
               <input id="search" type="text" placeholder="Rechercher…" />
               <button id="search-btn" title="Rechercher dans tous les messages">🔍</button>
             </div>
             <div class="search-hint" id="search-hint"></div>`
          : ""}
        <div class="rows" id="rows"><div class="empty">Chargement…</div></div>
      </ha-card>
    `;

    const search = root.getElementById("search");
    if (search) {
      search.addEventListener("input", (e) => {
        this._filter = (e.target.value || "").trim().toLowerCase();
        if (this._mode === "search") this._mode = "list";
        this._renderRows();
      });
      // Enter → search the whole message history of every conversation.
      search.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          this._runSearch();
        }
      });
    }
    const searchBtn = root.getElementById("search-btn");
    if (searchBtn) {
      searchBtn.addEventListener("click", () => this._runSearch());
    }
  }

  // ------------------------------------------------------------------
  // Global search (across every conversation)
  // ------------------------------------------------------------------

  async _runSearch() {
    const input = this.shadowRoot.getElementById("search");
    const query = ((input && input.value) || this._filter || "").trim();
    if (!query) return;
    this._filter = query.toLowerCase();
    this._searching = true;
    this._renderRows();
    try {
      const result = await this._hass.connection.sendMessagePromise({
        type: "simplex/search",
        query,
        limit: 100,
        ...(this._config.entry_id ? { entry_id: this._config.entry_id } : {}),
      });
      this._searchResults = result.results || [];
      this._searchCount = result.count || 0;
    } catch (err) {
      this._searchResults = [];
      this._searchCount = 0;
      this._renderError(err.message || String(err));
    } finally {
      this._searching = false;
      this._mode = "search";
      this._renderRows();
    }
  }

  _renderSearchRows() {
    const el = this.shadowRoot.getElementById("rows");
    if (!el) return;
    const results = this._searchResults || [];
    if (!results.length) {
      el.innerHTML = '<div class="empty">Aucun message ne correspond à cette recherche.</div>';
      return;
    }
    const query = (this._filter || "").toLowerCase();
    el.innerHTML = results
      .map((group) => {
        const snippets = (group.messages || [])
          .slice(0, 3)
          .map((m) => {
            const text = m.file
              ? `📎 ${m.file.name || "Fichier"}`
              : m.text || "";
            return `<div class="snippet">${this._highlight(text, query)}</div>`;
          })
          .join("");
        const more = (group.messages || []).length > 3
          ? `<div class="snippet">… ${group.messages.length - 3} autre(s)</div>`
          : "";
        return `
          <div class="row" data-alias="${this._escape(group.alias || "")}">
            <div class="avatar" style="background:${this._avatarColor(group.alias)}">${
              group.type === "group" ? "👥" : this._initial(group.name)
            }</div>
            <div class="body">
              <div class="name-row">
                <span class="name">${this._escape(group.name || group.alias || "?")}</span>
                <span class="time">${group.messages ? group.messages.length : 0} résultat(s)</span>
              </div>
              ${snippets}
              ${more}
            </div>
          </div>`;
      })
      .join("");

    el.querySelectorAll(".row").forEach((rowEl) => {
      rowEl.addEventListener("click", () => this._onRowClick(rowEl.dataset.alias));
    });
  }

  _highlight(text, query) {
    const safe = this._escape(text);
    if (!query) return safe;
    // The text is HTML-escaped, so the query has to be escaped the same way
    // for the match to be found.
    const escaped = this._escape(query).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    try {
      return safe.replace(new RegExp(`(${escaped})`, "gi"), "<mark>$1</mark>");
    } catch (e) {
      return safe;
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

    const hint = this.shadowRoot.getElementById("search-hint");
    const btn = this.shadowRoot.getElementById("search-btn");
    if (btn) btn.disabled = this._searching;

    if (this._mode === "search") {
      if (hint) {
        hint.innerHTML = this._searching
          ? "Recherche en cours…"
          : `${this._searchCount} message(s) trouvé(s) · <button class="back-btn" id="back-btn">← conversations</button>`;
      }
      const back = this.shadowRoot.getElementById("back-btn");
      if (back) {
        back.addEventListener("click", () => {
          this._mode = "list";
          this._renderRows();
        });
      }
      this._renderSearchRows();
      return;
    }

    if (hint) {
      hint.textContent = this._filter
        ? "Filtre local · Entrée pour chercher dans tous les messages"
        : "Entrée pour chercher dans tous les messages";
    }

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

if (!customElements.get("simplex-conversations-card")) customElements.define("simplex-conversations-card", SimplexConversationsCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "simplex-conversations-card",
  name: "SimpleX Conversations",
  description: "Écran d'accueil façon appli SimpleX : liste des contacts avec aperçu du dernier message et badge non-lus.",
});
