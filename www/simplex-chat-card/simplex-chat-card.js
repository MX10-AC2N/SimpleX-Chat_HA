/**
 * SimpleX Chat Card
 * -----------------------------------------------------------------------
 * A full conversation-thread card styled after the SimpleX Chat Android
 * app: a dark header bar with the contact name, a scrolling column of
 * message bubbles (yours on the right, theirs on the left, timestamps),
 * and a composer bar (text + voice + video) at the bottom.
 *
 * Backend requirements (provided by the `simplex` custom integration,
 * v2.1+):
 *   - HA websocket command "simplex/history" → initial message list
 *   - HA websocket command "simplex/contacts" → display names + live state
 *   - HA event "simplex_message_received" → live updates
 *   - services simplex.send_message / simplex.send_file (via /api/simplex/upload)
 *
 * Install: copy this file to /config/www/simplex-chat-card/ and add it as
 * a Lovelace resource:
 *   URL:  /local/simplex-chat-card/simplex-chat-card.js
 *   Type: JavaScript Module
 *
 * Card config example:
 *   type: custom:simplex-chat-card
 *   alias: family
 *   title: Famille            # optional, defaults to the alias
 *   history_limit: 50         # optional, default 50
 *
 * Dynamic mode — ONE generic view for every contact:
 *   type: custom:simplex-chat-card
 *   alias: auto               # or simply omit the key
 *
 * In dynamic mode the card reads the alias from the URL:
 *   - the hash      → /simplex-chat#alice  (survives a page reload)
 *   - the last path segment → /simplex-chat/alice
 *
 * That is what makes the conversation list card work out of the box with
 * auto-discovered contacts: no view has to be declared per contact.
 * -----------------------------------------------------------------------
 */

const UPLOAD_URL = "/api/simplex/upload";
const MAX_RECORD_SECONDS = 120;
// The CLI carries the item ids on a single command line — cap the batch.
const MAX_MARK_READ_IDS = 50;

class SimplexChatCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = null;
    this._messages = [];
    this._unsubscribe = null;
    this._loaded = false;
    this._hasMore = false;
    this._loadingMore = false;
    this._recorder = null;
    this._recordedChunks = [];
    this._recordKind = null;
    this._stream = null;
    this._timerHandle = null;
    this._recordStart = 0;
    this._alias = null; // the alias actually in use
    this._displayName = null;
    this._contactType = "contact";
    this._contacts = null; // alias → target, from "simplex/contacts"
    this._locationHandler = null;
  }

  setConfig(config) {
    const dynamic = !config.alias || config.alias === "auto";
    this._config = {
      dynamic,
      alias: dynamic ? null : config.alias,
      title: config.title || null,
      history_limit: config.history_limit || 50,
      entry_id: config.entry_id || null,
      connection_entity:
        config.connection_entity || "binary_sensor.simplex_chat_connection",
      auto_mark_read: config.auto_mark_read !== false,
    };
    this._alias = this._config.alias;
    this._renderShell();
    if (this._config.dynamic) {
      this._bindLocation();
    }
  }

  set hass(hass) {
    const first = this._hass === null;
    this._hass = hass;
    if (first) {
      if (this._config.dynamic) {
        this._applyAlias(this._aliasFromLocation());
      } else {
        this._applyAlias(this._config.alias);
      }
      this._subscribe();
      this._loadContacts();
    }
  }

  getCardSize() {
    return 8;
  }

  disconnectedCallback() {
    if (this._unsubscribe) {
      this._unsubscribe();
      this._unsubscribe = null;
    }
    if (this._locationHandler) {
      window.removeEventListener("popstate", this._locationHandler);
      window.removeEventListener("hashchange", this._locationHandler);
      this._locationHandler = null;
    }
    if (this._timerHandle) window.clearInterval(this._timerHandle);
    if (this._stream) this._stream.getTracks().forEach((t) => t.stop());
  }

  // ------------------------------------------------------------------
  // Dynamic alias resolution
  // ------------------------------------------------------------------

  _aliasFromLocation() {
    // The hash is the primary carrier: it survives a page reload, while
    // the path is owned by Home Assistant's router.
    const hash = (window.location.hash || "").replace(/^#/, "").trim();
    if (hash) {
      try {
        return decodeURIComponent(hash.split("?")[0]);
      } catch (e) {
        return hash.split("?")[0];
      }
    }
    // Fallback: the conversation list stores the last chosen alias, in case
    // Home Assistant's router normalised the URL and dropped the hash.
    try {
      const stored = window.sessionStorage.getItem("simplex_chat_alias");
      if (stored) return stored;
    } catch (e) {
      /* private mode: the hash alone will do */
    }
    const segments = (window.location.pathname || "").split("/").filter(Boolean);
    return segments.length ? decodeURIComponent(segments[segments.length - 1]) : null;
  }

  _bindLocation() {
    this._locationHandler = () => {
      const alias = this._aliasFromLocation();
      if (alias && alias !== this._alias) {
        this._applyAlias(alias);
      }
    };
    window.addEventListener("popstate", this._locationHandler);
    window.addEventListener("hashchange", this._locationHandler);
    // Home Assistant's router does not always fire popstate for in-app
    // navigation, so also listen to its own event.
    window.addEventListener("location-changed", this._locationHandler);
  }

  _applyAlias(alias) {
    this._alias = alias || null;
    this._messages = [];
    this._loaded = false;
    this._hasMore = false;
    this._updateHeader();
    if (this._alias) {
      this._loadHistory();
    } else {
      this._renderMessages(true);
    }
  }

  // ------------------------------------------------------------------
  // Contacts / display names
  // ------------------------------------------------------------------

  async _loadContacts() {
    try {
      const result = await this._hass.connection.sendMessagePromise({
        type: "simplex/contacts",
        ...(this._config.entry_id ? { entry_id: this._config.entry_id } : {}),
      });
      this._contacts = result.targets || {};
      this._updateHeader();
    } catch (err) {
      // The contact list is a nicety (it only provides the pretty name);
      // a failure must not break the conversation itself.
      this._contacts = null;
    }
  }

  _contactInfo() {
    if (!this._contacts || !this._alias) return null;
    return this._contacts[this._alias] || null;
  }

  _updateHeader() {
    const info = this._contactInfo();
    const nameEl = this.shadowRoot.getElementById("header-name");
    const avatarEl = this.shadowRoot.getElementById("header-avatar");
    const subEl = this.shadowRoot.getElementById("status-line");
    const readBtn = this.shadowRoot.getElementById("read-btn");
    if (!nameEl || !avatarEl) return;

    this._contactType = (info && info.type) || "contact";
    const label =
      (info && info.name) ||
      this._config.title ||
      this._alias ||
      "SimpleX";
    this._displayName = label;
    nameEl.textContent = label;
    avatarEl.textContent = (label || "?").trim().charAt(0).toUpperCase();
    avatarEl.classList.toggle("group", !!(info && info.type === "group"));

    const unread = this._unreadIncoming();
    if (readBtn) {
      readBtn.hidden = unread.length === 0;
      readBtn.title = `Marquer ${unread.length} message(s) comme lu(s)`;
    }

    if (subEl && !this._recording) {
      const connected = this._isConnected();
      subEl.textContent = connected
        ? info && info.type === "group"
          ? "Groupe · connecté"
          : "Connecté"
        : "Hors ligne";
      subEl.className = connected ? "sub" : "sub offline";
    }
  }

  _isConnected() {
    if (!this._hass) return false;
    const state = this._hass.states[this._config.connection_entity];
    return !!state && state.state === "on";
  }

  _unreadIncoming() {
    const ids = this._messages
      .filter((m) => m.direction !== "outgoing" && m.item_id != null)
      .map((m) => m.item_id);
    // The CLI takes the ids on a single command line: keep the batch sane.
    return ids.slice(-MAX_MARK_READ_IDS);
  }

  // ------------------------------------------------------------------
  // Data loading
  // ------------------------------------------------------------------

  async _loadHistory() {
    if (!this._alias) return;
    try {
      const result = await this._hass.connection.sendMessagePromise({
        type: "simplex/history",
        alias: this._alias,
        limit: this._config.history_limit,
        ...(this._config.entry_id ? { entry_id: this._config.entry_id } : {}),
      });
      this._messages = (result.messages || []).slice();
      this._hasMore = !!result.has_more;
      this._loaded = true;
      this._renderMessages(true);
      this._attachScrollListener();
      this._updateHeader();
      if (this._config.auto_mark_read) {
        this._markRead(this._unreadIncoming(), true);
      }
    } catch (err) {
      this._renderError(err.message || String(err));
    }
  }

  // "Load older" — triggered when the user scrolls near the top of the
  // thread. Uses the oldest currently-loaded message's item_id as the
  // `before_item_id` cursor (see ws_api.py's "simplex/history" and
  // SimplexWsClient.get_chat_history for the underlying `/_get chat ...
  // before=<id> count=<limit>` command).
  _attachScrollListener() {
    const container = this.shadowRoot.getElementById("messages");
    if (!container || container.dataset.scrollBound) return;
    container.dataset.scrollBound = "1";
    container.addEventListener("scroll", () => {
      if (container.scrollTop < 60) this._loadOlder();
    });
  }

  async _loadOlder() {
    if (this._loadingMore || !this._hasMore || !this._messages.length) return;
    const sorted = this._messages.slice().sort((a, b) => (a.timestamp || "").localeCompare(b.timestamp || ""));
    const oldest = sorted[0];
    if (!oldest || !oldest.item_id) {
      // No usable cursor (e.g. the oldest loaded item has no item_id) —
      // nothing more we can safely page from.
      this._hasMore = false;
      return;
    }
    this._loadingMore = true;
    const container = this.shadowRoot.getElementById("messages");
    const prevHeight = container ? container.scrollHeight : 0;
    this._renderMessages(false, true);

    try {
      const result = await this._hass.connection.sendMessagePromise({
        type: "simplex/history",
        alias: this._alias,
        limit: this._config.history_limit,
        before_item_id: oldest.item_id,
        ...(this._config.entry_id ? { entry_id: this._config.entry_id } : {}),
      });
      const older = result.messages || [];
      this._hasMore = !!result.has_more;
      // Dedup by item_id in case of any overlap at the page boundary.
      const existingIds = new Set(this._messages.map((m) => m.item_id).filter((v) => v != null));
      const toPrepend = older.filter((m) => m.item_id == null || !existingIds.has(m.item_id));
      this._messages = toPrepend.concat(this._messages);
    } catch (err) {
      // eslint-disable-next-line no-console
      console.warn("simplex-chat-card: could not load older messages", err);
      this._hasMore = false;
    } finally {
      this._loadingMore = false;
      this._renderMessages(false);
      // Preserve the visual scroll position: after prepending, restore the
      // same distance from the (now taller) top instead of jumping.
      if (container) {
        const newHeight = container.scrollHeight;
        container.scrollTop += newHeight - prevHeight;
      }
    }
  }

  _subscribe() {
    this._hass.connection
      .subscribeEvents((event) => {
        const data = event.data || {};
        if (data.alias !== this._alias) return;
        this._messages.push(data);
        this._renderMessages(true);
        this._updateHeader();
        if (this._config.auto_mark_read) {
          this._markRead([data.item_id], true);
        }
      }, "simplex_message_received")
      .then((unsub) => {
        this._unsubscribe = unsub;
      })
      .catch((err) => {
        // eslint-disable-next-line no-console
        console.warn("simplex-chat-card: could not subscribe to events", err);
      });

    // Keep the header connection dot honest.
    this._hass.connection
      .subscribeEvents(() => this._updateHeader(), "state_changed")
      .then((unsub) => {
        this._stateUnsub = unsub;
      })
      .catch(() => {});
  }

  async _markRead(itemIds, silent) {
    const ids = (itemIds || []).filter((v) => v != null);
    if (!ids.length || !this._alias) return;
    try {
      await this._hass.callService("simplex", "mark_read", {
        alias: this._alias,
        item_ids: ids,
      });
      this._updateHeader();
    } catch (err) {
      if (!silent) {
        const statusLine = this.shadowRoot.getElementById("status-line");
        if (statusLine) statusLine.textContent = `Échec : ${err.message || err}`;
      }
    }
  }

  // ------------------------------------------------------------------
  // Rendering — shell (built once)
  // ------------------------------------------------------------------

  _renderShell() {
    const root = this.shadowRoot;
    root.innerHTML = `
      <style>
        :host { display: block; }
        ha-card {
          padding: 0;
          overflow: hidden;
          display: flex;
          flex-direction: column;
          height: 520px;
          background: var(--simplex-bg, #0b141a);
        }
        .header {
          display: flex; align-items: center; gap: 10px;
          padding: 10px 14px;
          background: var(--simplex-header-bg, #1b2b34);
          color: #fff;
          flex: 0 0 auto;
        }
        .header .avatar {
          width: 36px; height: 36px; border-radius: 50%;
          background: linear-gradient(135deg, #3fb37f, #2f9e6f);
          display: flex; align-items: center; justify-content: center;
          font-weight: 600; font-size: 1em;
          flex: 0 0 auto;
        }
        .header .avatar.group { background: linear-gradient(135deg, #4a7fd4, #3567b8); }
        .header .who { flex: 1 1 auto; min-width: 0; }
        .header .name { font-weight: 600; font-size: 1.05em; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .header .sub { font-size: 0.78em; opacity: 0.7; }
        .header .sub.offline { color: #e0a06a; opacity: 1; }
        .header .read-btn {
          border: none; background: #2f9e6f; color: #fff;
          border-radius: 14px; padding: 4px 10px; font-size: 0.75em;
          cursor: pointer; flex: 0 0 auto;
        }
        .header .read-btn[hidden] { display: none; }

        .messages {
          flex: 1 1 auto; overflow-y: auto;
          padding: 14px 10px;
          display: flex; flex-direction: column; gap: 6px;
          background-image:
            radial-gradient(circle at 20% 10%, rgba(255,255,255,0.03) 0, transparent 40%),
            radial-gradient(circle at 80% 80%, rgba(255,255,255,0.03) 0, transparent 40%);
        }
        .row { display: flex; }
        .row.out { justify-content: flex-end; }
        .row.in { justify-content: flex-start; }

        .day-sep {
          align-self: center;
          margin: 10px 0 4px;
          padding: 2px 10px;
          border-radius: 10px;
          background: rgba(255,255,255,0.08);
          color: #9fb3ba;
          font-size: 0.72em;
        }

        .bubble {
          max-width: 75%;
          padding: 7px 10px 6px 10px;
          border-radius: 10px;
          font-size: 0.92em;
          line-height: 1.32;
          position: relative;
          word-wrap: break-word;
          white-space: pre-wrap;
        }
        .bubble.out {
          background: var(--simplex-bubble-out, #2f9e6f);
          color: #f1fff6;
          border-bottom-right-radius: 2px;
        }
        .bubble.in {
          background: var(--simplex-bubble-in, #223139);
          color: #eef3f5;
          border-bottom-left-radius: 2px;
        }
        .bubble .sender {
          display: block; font-size: 0.72em; font-weight: 600;
          color: #6fd3ff; margin-bottom: 2px;
        }
        .bubble .meta {
          display: block; text-align: right; margin-top: 3px;
          font-size: 0.68em; opacity: 0.7;
        }
        .bubble .file {
          display: flex; align-items: center; gap: 6px;
          font-size: 0.9em; opacity: 0.9; margin-bottom: 2px;
        }
        .bubble .file svg { width: 16px; height: 16px; fill: currentColor; }
        .bubble img.media { max-width: 100%; border-radius: 6px; display: block; margin-bottom: 4px; cursor: zoom-in; }
        .bubble audio.media, .bubble video.media { max-width: 100%; display: block; margin-bottom: 4px; }
        .bubble video.media { border-radius: 6px; }
        .ticks { display: inline-flex; margin-left: 4px; vertical-align: middle; }
        .ticks svg { width: 13px; height: 13px; fill: currentColor; }
        .ticks.read svg { fill: #6fd3ff; }
        .empty, .error {
          color: #9fb3ba; text-align: center; margin-top: 30px; font-size: 0.9em;
        }
        .error { color: #e08a8a; }
        .load-older {
          color: #7d939a; text-align: center; font-size: 0.8em;
          padding: 8px 0 4px;
        }

        .composer {
          flex: 0 0 auto;
          display: flex; align-items: center; gap: 8px;
          padding: 8px 10px;
          background: var(--simplex-header-bg, #1b2b34);
        }
        .composer input[type="text"] {
          flex: 1; border: none; border-radius: 18px;
          padding: 9px 14px; font-size: 0.95em;
          background: #0f1b21; color: #eef3f5;
        }
        .composer input[type="text"]::placeholder { color: #7d939a; }
        .icon-btn {
          width: 38px; height: 38px; border-radius: 50%; border: none;
          background: #223139; color: #cfe3e9;
          display: flex; align-items: center; justify-content: center;
          cursor: pointer; flex: 0 0 auto;
        }
        .icon-btn.recording { background: #c0493e; color: #fff; animation: pulse 1.2s infinite; }
        .icon-btn.send { background: #2f9e6f; color: #fff; }
        .icon-btn svg { width: 19px; height: 19px; fill: currentColor; }
        @keyframes pulse { 0%{opacity:1;} 50%{opacity:0.55;} 100%{opacity:1;} }

        video.preview {
          position: absolute; bottom: 70px; right: 14px;
          width: 110px; border-radius: 8px; background: #000;
          display: none; z-index: 2;
        }
        video.preview.active { display: block; }
      </style>
      <ha-card>
        <div class="header">
          <div class="avatar" id="header-avatar">S</div>
          <div class="who">
            <div class="name" id="header-name">SimpleX</div>
            <div class="sub" id="status-line">SimpleX Chat</div>
          </div>
          <button class="read-btn" id="read-btn" hidden>Marquer lu</button>
        </div>
        <div class="messages" id="messages"><div class="empty">Chargement…</div></div>
        <video class="preview" id="preview" autoplay muted playsinline></video>
        <div class="composer">
          <button class="icon-btn" id="mic-btn" title="Message vocal">${this._iconMic()}</button>
          <button class="icon-btn" id="cam-btn" title="Message vidéo">${this._iconCam()}</button>
          <input id="text-input" type="text" placeholder="Écrire un message…" />
          <button class="icon-btn send" id="send-btn" title="Envoyer">${this._iconSend()}</button>
        </div>
      </ha-card>
    `;

    root.getElementById("send-btn").addEventListener("click", () => this._sendText());
    root.getElementById("text-input").addEventListener("keydown", (e) => {
      if (e.key === "Enter") this._sendText();
    });
    root.getElementById("mic-btn").addEventListener("click", () => this._toggleRecord("audio"));
    root.getElementById("cam-btn").addEventListener("click", () => this._toggleRecord("video"));
    const readBtn = root.getElementById("read-btn");
    if (readBtn) {
      readBtn.addEventListener("click", () => this._markRead(this._unreadIncoming(), false));
    }
    this._updateHeader();
  }

  _iconMic() {
    return '<svg viewBox="0 0 24 24"><path d="M12 14a3 3 0 0 0 3-3V5a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-3.08A7 7 0 0 0 19 11h-2z"/></svg>';
  }
  _iconCam() {
    return '<svg viewBox="0 0 24 24"><path d="M17 10.5V7a1 1 0 0 0-1-1H4a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-3.5l4 4v-11l-4 4z"/></svg>';
  }
  _iconSend() {
    return '<svg viewBox="0 0 24 24"><path d="M3 20l18-8L3 4v6l12 2-12 2z"/></svg>';
  }
  _iconFile() {
    return '<svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/></svg>';
  }

  _escape(str) {
    const d = document.createElement("div");
    d.textContent = str || "";
    return d.innerHTML;
  }

  _initial(name) {
    return this._escape((name || "?").trim().charAt(0).toUpperCase());
  }

  // ------------------------------------------------------------------
  // Rendering — messages (re-rendered on every update)
  // ------------------------------------------------------------------

  _renderError(message) {
    const el = this.shadowRoot.getElementById("messages");
    if (el) el.innerHTML = `<div class="error">${this._escape(message)}</div>`;
  }

  // `showLoadingTop`: renders a small spinner row above the oldest message
  // while a "load older" page is in flight (set by _loadOlder(); callers
  // doing a normal render leave it undefined/false).
  _renderMessages(scrollToBottom, showLoadingTop) {
    const container = this.shadowRoot.getElementById("messages");
    if (!container) return;

    if (!this._alias) {
      container.innerHTML =
        '<div class="empty">Aucune conversation sélectionnée. Choisissez un contact dans la liste.</div>';
      return;
    }

    if (!this._messages.length) {
      container.innerHTML = this._loaded
        ? '<div class="empty">Aucun message pour l\'instant.</div>'
        : '<div class="empty">Chargement…</div>';
      return;
    }

    const sorted = this._messages
      .slice()
      .sort((a, b) => (a.timestamp || "").localeCompare(b.timestamp || ""));

    const loaderHtml = showLoadingTop
      ? '<div class="load-older">Chargement des messages précédents…</div>'
      : "";

    let lastDay = null;
    let html = "";
    for (const m of sorted) {
      const day = this._dayKey(m.timestamp);
      if (day && day !== lastDay) {
        html += `<div class="day-sep">${this._escape(this._dayLabel(m.timestamp))}</div>`;
        lastDay = day;
      }
      const dir = m.direction === "outgoing" ? "out" : "in";
      const time = this._formatTime(m.timestamp);
      const fileHtml = this._renderFile(m.file);
      const textHtml = m.text ? this._escape(m.text) : "";
      const ticksHtml = dir === "out" ? this._renderTicks(m.status) : "";
      const senderHtml =
        dir === "in" && this._contactType === "group" && m.sender
          ? `<span class="sender">${this._escape(m.sender)}</span>`
          : "";
      html += `
        <div class="row ${dir}">
          <div class="bubble ${dir}">
            ${senderHtml}
            ${fileHtml}
            ${textHtml}
            <span class="meta">${time}${m.edited ? " · modifié" : ""}${ticksHtml}</span>
          </div>
        </div>`;
    }

    container.innerHTML = loaderHtml + html;

    if (scrollToBottom) {
      container.scrollTop = container.scrollHeight;
    }
  }

  _renderFile(file) {
    if (!file) return "";
    const name = this._escape(file.name || "Fichier");
    if (!file.media_url) {
      // Received but not yet playable here (still transferring, or the
      // shared inbox volume isn't configured — see DOCKER.md).
      return `<div class="file">${this._iconFile()}<span>${name}</span></div>`;
    }
    const url = this._escape(file.media_url);
    if (file.kind === "image") {
      return `<img class="media" src="${url}" alt="${name}" />`;
    }
    if (file.kind === "voice") {
      return `<audio class="media" controls src="${url}"></audio>`;
    }
    if (file.kind === "file" && /\.(mp4|webm|mov)$/i.test(file.name || "")) {
      return `<video class="media" controls src="${url}"></video>`;
    }
    return `<div class="file">${this._iconFile()}<a href="${url}" target="_blank" rel="noopener" style="color:inherit;">${name}</a></div>`;
  }

  _renderTicks(status) {
    // ✓ sent, ✓✓ delivered, ✓✓ (blue) read. Best-effort — see
    // normalize_chat_item()'s docstring on why this can stay "sent" even
    // once a message truly was delivered/read, depending on CLI version.
    const double = status === "delivered" || status === "read";
    const cls = status === "read" ? "ticks read" : "ticks";
    const check = '<svg viewBox="0 0 24 24"><path d="M9 16.2L4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4z"/></svg>';
    return `<span class="${cls}">${check}${double ? check : ""}</span>`;
  }

  _dayKey(ts) {
    const d = this._parseDate(ts);
    if (!d) return null;
    return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
  }

  _dayLabel(ts) {
    const d = this._parseDate(ts);
    if (!d) return "";
    const today = new Date();
    const yesterday = new Date();
    yesterday.setDate(today.getDate() - 1);
    const same = (a, b) =>
      a.getFullYear() === b.getFullYear() &&
      a.getMonth() === b.getMonth() &&
      a.getDate() === b.getDate();
    if (same(d, today)) return "Aujourd'hui";
    if (same(d, yesterday)) return "Hier";
    return d.toLocaleDateString([], { day: "2-digit", month: "long", year: "numeric" });
  }

  _parseDate(ts) {
    if (!ts) return null;
    const d = new Date(ts);
    return Number.isNaN(d.getTime()) ? null : d;
  }

  _formatTime(ts) {
    const d = this._parseDate(ts);
    if (!d) return "";
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  // ------------------------------------------------------------------
  // Sending — text
  // ------------------------------------------------------------------

  async _sendText() {
    const input = this.shadowRoot.getElementById("text-input");
    const message = (input.value || "").trim();
    if (!message) return;
    if (!this._alias) {
      this._setStatus("Aucune conversation sélectionnée.");
      return;
    }
    const statusLine = this.shadowRoot.getElementById("status-line");
    try {
      await this._hass.callService("simplex", "send_message", {
        alias: this._alias,
        message,
      });
      input.value = "";
      this._setStatus(null);
    } catch (err) {
      this._setStatus(`Échec : ${err.message || err}`);
    }
  }

  _setStatus(text) {
    if (this._recording) return;
    const statusLine = this.shadowRoot.getElementById("status-line");
    if (!statusLine) return;
    if (text) {
      statusLine.textContent = text;
      statusLine.className = "sub offline";
    } else {
      this._updateHeader();
    }
  }

  // ------------------------------------------------------------------
  // Sending — voice / video (recorded clip, see DOCKER.md for the shared
  // outbox volume this relies on)
  // ------------------------------------------------------------------

  async _toggleRecord(kind) {
    if (this._recorder && this._recorder.state === "recording") {
      this._recorder.stop();
      return;
    }
    if (!this._alias) {
      this._setStatus("Aucune conversation sélectionnée.");
      return;
    }
    try {
      await this._startRecording(kind);
    } catch (err) {
      this._setStatus(`Micro/caméra indisponible : ${err.message || err}`);
    }
  }

  async _startRecording(kind) {
    const constraints = kind === "video" ? { audio: true, video: true } : { audio: true };
    this._stream = await navigator.mediaDevices.getUserMedia(constraints);

    const preview = this.shadowRoot.getElementById("preview");
    if (kind === "video") {
      preview.srcObject = this._stream;
      preview.classList.add("active");
    }

    const mimeType =
      kind === "video"
        ? this._pickMime(["video/webm;codecs=vp8,opus", "video/webm"])
        : this._pickMime(["audio/webm;codecs=opus", "audio/webm"]);

    this._recordedChunks = [];
    this._recordKind = kind;
    this._recorder = new MediaRecorder(this._stream, mimeType ? { mimeType } : undefined);
    this._recorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) this._recordedChunks.push(e.data);
    };
    this._recorder.onstop = () => this._onRecordingStop();
    this._recorder.start();

    this._recordStart = Date.now();
    this._recording = true;
    this._setRecordingUi(kind, true);
    const statusLine = this.shadowRoot.getElementById("status-line");
    this._timerHandle = window.setInterval(() => {
      const elapsed = Math.floor((Date.now() - this._recordStart) / 1000);
      if (statusLine) statusLine.textContent = `Enregistrement… ${elapsed}s`;
      if (elapsed >= MAX_RECORD_SECONDS) this._recorder.stop();
    }, 500);
  }

  _pickMime(candidates) {
    for (const c of candidates) {
      if (window.MediaRecorder && MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(c)) {
        return c;
      }
    }
    return null;
  }

  _setRecordingUi(kind, recording) {
    const btnId = kind === "audio" ? "mic-btn" : "cam-btn";
    const otherId = kind === "audio" ? "cam-btn" : "mic-btn";
    const btn = this.shadowRoot.getElementById(btnId);
    const other = this.shadowRoot.getElementById(otherId);
    if (btn) btn.classList.toggle("recording", recording);
    if (other) other.disabled = recording;
  }

  async _onRecordingStop() {
    if (this._timerHandle) {
      window.clearInterval(this._timerHandle);
      this._timerHandle = null;
    }
    this._recording = false;
    this._setRecordingUi(this._recordKind, false);
    const preview = this.shadowRoot.getElementById("preview");
    if (preview) {
      preview.classList.remove("active");
      preview.srcObject = null;
    }
    if (this._stream) {
      this._stream.getTracks().forEach((t) => t.stop());
      this._stream = null;
    }

    const mimeType = this._recorder.mimeType || (this._recordKind === "audio" ? "audio/webm" : "video/webm");
    const blob = new Blob(this._recordedChunks, { type: mimeType });
    this._recordedChunks = [];

    const statusLine = this.shadowRoot.getElementById("status-line");
    if (blob.size === 0) {
      if (statusLine) statusLine.textContent = "Enregistrement vide, rien envoyé.";
      return;
    }
    await this._upload(blob, this._recordKind);
  }

  async _upload(blob, kind) {
    const statusLine = this.shadowRoot.getElementById("status-line");
    if (statusLine) statusLine.textContent = "Envoi en cours…";
    const form = new FormData();
    form.append("alias", this._alias);
    form.append("kind", kind);
    form.append("file", blob, "clip.webm");
    if (this._config.entry_id) form.append("entry_id", this._config.entry_id);

    try {
      const token = this._hass?.auth?.data?.access_token;
      const resp = await fetch(UPLOAD_URL, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: form,
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok || !data.success) {
        throw new Error(data.error || `HTTP ${resp.status}`);
      }
      this._setStatus(null);
    } catch (err) {
      if (statusLine) statusLine.textContent = `Échec de l'envoi : ${err.message || err}`;
    }
  }
}

customElements.define("simplex-chat-card", SimplexChatCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "simplex-chat-card",
  name: "SimpleX Chat",
  description: "Fil de discussion complet (bulles, historique, temps réel) façon appli SimpleX Chat Android.",
});
