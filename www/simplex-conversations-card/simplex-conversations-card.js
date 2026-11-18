/**
 * SimpleX Conversations Card
 * -----------------------------------------------------------------------
 * The "home screen" of a messaging app: one row per configured SimpleX
 * contact/group, with an avatar, the last message preview, a timestamp and
 * an unread badge (when the CLI reports one — see note below). Tapping a
 * row navigates to a configured dashboard view (meant to hold a
 * `simplex-chat-card` for that same alias).
 *
 * Backend requirement: the `simplex` integration's HA websocket command
 * "simplex/conversations" (v2.2+, now backed by `/chats all` since v2.3 so
 * households with more than 20 contacts all show up — see DOCKER.md).
 *
 * Note on unread badges: reads `chatStats.unreadCount`, confirmed present
 * on every chat preview (checked against the CLI's own Haskell source,
 * v7.1.4 — the version pinned in mx10-ac2n/simplex-bridge, see ws_api.py).
 * The `.get()` check is kept as plain defensive coding; when it's absent
 * the row just shows no badge rather than a guessed/wrong count.
 *
 * Install: copy this file to /config/www/simplex-conversations-card/ and
 * add it as a Lovelace resource:
 *   URL:  /local/simplex-conversations-card/simplex-conversations-card.js
 *   Type: JavaScript Module
 *
 * Card config example:
 *   type: custom:simplex-conversations-card
 *   title: SimpleX
 *   navigate_prefix: /simplex-   # + alias, e.g. /simplex-family
 * -----------------------------------------------------------------------
 */

class SimplexConversationsCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = null;
    this._conversations = [];
    this._unsubscribe = null;
    this._loaded = false;
  }

  setConfig(config) {
    this._config = {
      title: config.title || "SimpleX",
      navigate_prefix: config.navigate_prefix || null,
      entry_id: config.entry_id || null,
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
    this._hass.connection
      .subscribeEvents(() => this._load(), "simplex_message_received")
      .then((unsub) => {
        this._unsubscribe = unsub;
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
          color: #fff;
        }
        .rows { display: flex; flex-direction: column; }
        .row {
          display: flex; align-items: center; gap: 12px;
          padding: 10px 16px; cursor: pointer;
          border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        .row:hover { background: rgba(255,255,255,0.04); }
        .avatar {
          width: 44px; height: 44px; border-radius: 50%; flex: 0 0 auto;
          background: linear-gradient(135deg, #3fb37f, #2f9e6f);
          display: flex; align-items: center; justify-content: center;
          color: #fff; font-weight: 600;
        }
        .body { flex: 1 1 auto; min-width: 0; }
        .name-row { display: flex; justify-content: space-between; gap: 8px; }
        .name { color: #eef3f5; font-weight: 600; font-size: 0.97em; }
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
        <div class="header">${this._escape(this._config.title)}</div>
        <div class="rows" id="rows"><div class="empty">Chargement…</div></div>
      </ha-card>
    `;
  }

  _renderError(message) {
    const el = this.shadowRoot.getElementById("rows");
    if (el) el.innerHTML = `<div class="error">${this._escape(message)}</div>`;
  }

  _renderRows() {
    const el = this.shadowRoot.getElementById("rows");
    if (!el) return;
    if (!this._conversations.length) {
      el.innerHTML = this._loaded
        ? '<div class="empty">Aucun contact configuré.</div>'
        : '<div class="empty">Chargement…</div>';
      return;
    }

    el.innerHTML = this._conversations
      .map((c) => {
        const last = c.last_message;
        const preview = last ? (last.file ? `📎 ${this._escape(last.file.name || "Fichier")}` : this._escape(last.text || "")) : "";
        const time = last ? this._formatTime(last.timestamp) : "";
        const badge =
          c.unread_count && c.unread_count > 0
            ? `<div class="badge">${c.unread_count > 99 ? "99+" : c.unread_count}</div>`
            : "";
        return `
          <div class="row" data-alias="${this._escape(c.alias)}">
            <div class="avatar">${this._initial(c.name)}</div>
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

  _onRowClick(alias) {
    if (!this._config.navigate_prefix) return;
    const path = `${this._config.navigate_prefix}${alias}`;
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
    return sameDay
      ? d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
      : d.toLocaleDateString([], { day: "2-digit", month: "2-digit" });
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
