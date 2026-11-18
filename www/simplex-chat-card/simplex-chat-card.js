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
 * -----------------------------------------------------------------------
 */

const UPLOAD_URL = "/api/simplex/upload";
const MAX_RECORD_SECONDS = 120;

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
  }

  setConfig(config) {
    if (!config.alias) {
      throw new Error("simplex-chat-card: 'alias' is required in the card config");
    }
    this._config = {
      alias: config.alias,
      title: config.title || config.alias,
      history_limit: config.history_limit || 50,
      entry_id: config.entry_id || null,
    };
    this._renderShell();
  }

  set hass(hass) {
    const first = this._hass === null;
    this._hass = hass;
    if (first) {
      this._loadHistory();
      this._subscribe();
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
    if (this._timerHandle) window.clearInterval(this._timerHandle);
    if (this._stream) this._stream.getTracks().forEach((t) => t.stop());
  }

  // ------------------------------------------------------------------
  // Data loading
  // ------------------------------------------------------------------

  async _loadHistory() {
    try {
      const result = await this._hass.connection.sendMessagePromise({
        type: "simplex/history",
        alias: this._config.alias,
        limit: this._config.history_limit,
        ...(this._config.entry_id ? { entry_id: this._config.entry_id } : {}),
      });
      this._messages = (result.messages || []).slice();
      this._hasMore = !!result.has_more;
      this._loaded = true;
      this._renderMessages(true);
      this._attachScrollListener();
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
        alias: this._config.alias,
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
        if (data.alias !== this._config.alias) return;
        this._messages.push(data);
        this._renderMessages(true);
      }, "simplex_message_received")
      .then((unsub) => {
        this._unsubscribe = unsub;
      })
      .catch((err) => {
        // eslint-disable-next-line no-console
        console.warn("simplex-chat-card: could not subscribe to events", err);
      });
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
        }
        .header .name { font-weight: 600; font-size: 1.05em; }
        .header .sub { font-size: 0.78em; opacity: 0.7; }

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
        .bubble .meta {
          display: block; text-align: right; margin-top: 3px;
          font-size: 0.68em; opacity: 0.7;
        }
        .bubble .file {
          display: flex; align-items: center; gap: 6px;
          font-size: 0.9em; opacity: 0.9; margin-bottom: 2px;
        }
        .bubble .file svg { width: 16px; height: 16px; fill: currentColor; }
        .bubble img.media { max-width: 100%; border-radius: 6px; display: block; margin-bottom: 4px; }
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
          <div class="avatar">${this._initial(this._config.title)}</div>
          <div>
            <div class="name">${this._escape(this._config.title)}</div>
            <div class="sub" id="status-line">SimpleX Chat</div>
          </div>
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

    container.innerHTML =
      loaderHtml +
      sorted
        .map((m) => {
          const dir = m.direction === "outgoing" ? "out" : "in";
          const time = this._formatTime(m.timestamp);
          const fileHtml = this._renderFile(m.file);
          const textHtml = m.text ? this._escape(m.text) : "";
          const ticksHtml = dir === "out" ? this._renderTicks(m.status) : "";
          return `
          <div class="row ${dir}">
            <div class="bubble ${dir}">
              ${fileHtml}
              ${textHtml}
              <span class="meta">${time}${m.edited ? " · modifié" : ""}${ticksHtml}</span>
            </div>
          </div>`;
        })
        .join("");

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

  _formatTime(ts) {
    if (!ts) return "";
    const d = new Date(ts);
    if (Number.isNaN(d.getTime())) return "";
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  // ------------------------------------------------------------------
  // Sending — text
  // ------------------------------------------------------------------

  async _sendText() {
    const input = this.shadowRoot.getElementById("text-input");
    const message = (input.value || "").trim();
    if (!message) return;
    const statusLine = this.shadowRoot.getElementById("status-line");
    try {
      await this._hass.callService("simplex", "send_message", {
        alias: this._config.alias,
        message,
      });
      input.value = "";
      if (statusLine) statusLine.textContent = "SimpleX Chat";
    } catch (err) {
      if (statusLine) statusLine.textContent = `Échec : ${err.message || err}`;
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
    try {
      await this._startRecording(kind);
    } catch (err) {
      const statusLine = this.shadowRoot.getElementById("status-line");
      if (statusLine) statusLine.textContent = `Micro/caméra indisponible : ${err.message || err}`;
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
    form.append("alias", this._config.alias);
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
      if (statusLine) statusLine.textContent = "SimpleX Chat";
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
