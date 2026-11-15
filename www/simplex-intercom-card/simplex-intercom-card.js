/**
 * SimpleX Intercom Card
 * -----------------------------------------------------------------------
 * A Lovelace card meant for a wall-mounted / living-room tablet. Lets
 * someone send a text message, a recorded voice clip, or a recorded video
 * clip to a SimpleX Chat contact configured in the `simplex` integration.
 *
 * It talks to a single backend endpoint registered by the integration:
 *   POST /api/simplex/upload   (multipart/form-data: alias, kind, file)
 *
 * Install: copy this file to /config/www/simplex-intercom-card/ and add it
 * as a Lovelace resource (Settings → Dashboards → Resources):
 *   URL:  /local/simplex-intercom-card/simplex-intercom-card.js
 *   Type: JavaScript Module
 *
 * Card config example:
 *   type: custom:simplex-intercom-card
 *   title: Salon → Famille
 *   aliases:
 *     - alice
 *     - family
 *   default_alias: family
 * -----------------------------------------------------------------------
 */

const UPLOAD_URL = "/api/simplex/upload";
const MAX_RECORD_SECONDS = 120;

class SimplexIntercomCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = null;
    this._recorder = null;
    this._recordedChunks = [];
    this._recordKind = null; // "audio" | "video"
    this._stream = null;
    this._timerHandle = null;
    this._recordStart = 0;
    this._status = { text: "", kind: "idle" }; // kind: idle|busy|error|success
  }

  setConfig(config) {
    if (!config.aliases || !Array.isArray(config.aliases) || config.aliases.length === 0) {
      throw new Error("simplex-intercom-card: 'aliases' (list) is required in the card config");
    }
    this._config = {
      title: config.title || "SimpleX Intercom",
      aliases: config.aliases,
      default_alias: config.default_alias || config.aliases[0],
      entry_id: config.entry_id || null,
    };
    this._selectedAlias = this._config.default_alias;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
  }

  getCardSize() {
    return 4;
  }

  // ------------------------------------------------------------------
  // Rendering
  // ------------------------------------------------------------------

  _render() {
    const root = this.shadowRoot;
    root.innerHTML = `
      <style>
        ha-card { padding: 16px; }
        .header { font-size: 1.1em; font-weight: 500; margin-bottom: 12px; }
        .alias-row { margin-bottom: 12px; }
        select, input[type="text"] {
          width: 100%;
          box-sizing: border-box;
          padding: 10px;
          border-radius: 8px;
          border: 1px solid var(--divider-color, #ccc);
          background: var(--card-background-color, #fff);
          color: var(--primary-text-color, #000);
          font-size: 1em;
        }
        .text-row { display: flex; gap: 8px; margin-bottom: 14px; }
        .text-row input { flex: 1; }
        button.send {
          border: none; border-radius: 8px; padding: 0 16px;
          background: var(--primary-color, #03a9f4); color: white;
          font-weight: 500; cursor: pointer;
        }
        .rec-row { display: flex; gap: 12px; margin-bottom: 10px; }
        .rec-btn {
          flex: 1; display: flex; flex-direction: column; align-items: center;
          gap: 6px; padding: 16px 8px; border-radius: 12px; border: none;
          background: var(--secondary-background-color, #f0f0f0);
          color: var(--primary-text-color, #000);
          cursor: pointer; font-size: 0.95em;
        }
        .rec-btn.recording {
          background: var(--error-color, #db4437); color: white;
          animation: pulse 1.2s infinite;
        }
        @keyframes pulse { 0%{opacity:1;} 50%{opacity:0.6;} 100%{opacity:1;} }
        .rec-btn svg { width: 28px; height: 28px; fill: currentColor; }
        video.preview {
          width: 100%; border-radius: 8px; margin-top: 8px;
          background: #000; display: none;
        }
        video.preview.active { display: block; }
        .status {
          margin-top: 10px; font-size: 0.9em; min-height: 1.2em;
        }
        .status.error { color: var(--error-color, #db4437); }
        .status.success { color: var(--success-color, #43a047); }
        .status.busy { color: var(--secondary-text-color, #888); }
      </style>
      <ha-card>
        <div class="header">${this._escape(this._config.title)}</div>
        ${this._config.aliases.length > 1
          ? `<div class="alias-row">
               <select id="alias-select">
                 ${this._config.aliases
                   .map(
                     (a) =>
                       `<option value="${this._escape(a)}" ${a === this._selectedAlias ? "selected" : ""}>${this._escape(a)}</option>`
                   )
                   .join("")}
               </select>
             </div>`
          : ""}
        <div class="text-row">
          <input id="text-input" type="text" placeholder="Écrire un message…" />
          <button class="send" id="send-text-btn">Envoyer</button>
        </div>
        <div class="rec-row">
          <button class="rec-btn" id="mic-btn">
            <svg viewBox="0 0 24 24"><path d="M12 14a3 3 0 0 0 3-3V5a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-3.08A7 7 0 0 0 19 11h-2z"/></svg>
            <span id="mic-label">Message vocal</span>
          </button>
          <button class="rec-btn" id="cam-btn">
            <svg viewBox="0 0 24 24"><path d="M17 10.5V7a1 1 0 0 0-1-1H4a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-3.5l4 4v-11l-4 4z"/></svg>
            <span id="cam-label">Message vidéo</span>
          </button>
        </div>
        <video class="preview" id="preview" autoplay muted playsinline></video>
        <div class="status" id="status"></div>
      </ha-card>
    `;

    root.getElementById("send-text-btn").addEventListener("click", () => this._sendText());
    root.getElementById("text-input").addEventListener("keydown", (e) => {
      if (e.key === "Enter") this._sendText();
    });
    root.getElementById("mic-btn").addEventListener("click", () => this._toggleRecord("audio"));
    root.getElementById("cam-btn").addEventListener("click", () => this._toggleRecord("video"));
    const aliasSelect = root.getElementById("alias-select");
    if (aliasSelect) {
      aliasSelect.addEventListener("change", (e) => {
        this._selectedAlias = e.target.value;
      });
    }
  }

  _escape(str) {
    const d = document.createElement("div");
    d.textContent = str;
    return d.innerHTML;
  }

  _setStatus(text, kind = "idle") {
    this._status = { text, kind };
    const el = this.shadowRoot.getElementById("status");
    if (!el) return;
    el.textContent = text;
    el.className = `status ${kind}`;
  }

  // ------------------------------------------------------------------
  // Text message
  // ------------------------------------------------------------------

  async _sendText() {
    const input = this.shadowRoot.getElementById("text-input");
    const message = (input.value || "").trim();
    if (!message) return;
    this._setStatus("Envoi…", "busy");
    try {
      await this._hass.callService("simplex", "send_message", {
        alias: this._selectedAlias,
        message,
      });
      input.value = "";
      this._setStatus("Envoyé ✓", "success");
    } catch (err) {
      this._setStatus(`Échec : ${err.message || err}`, "error");
    }
  }

  // ------------------------------------------------------------------
  // Audio / video recording
  // ------------------------------------------------------------------

  async _toggleRecord(kind) {
    if (this._recorder && this._recorder.state === "recording") {
      this._recorder.stop();
      return;
    }
    try {
      await this._startRecording(kind);
    } catch (err) {
      this._setStatus(`Micro/caméra indisponible : ${err.message || err}`, "error");
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

    const mimeType = kind === "video" ? this._pickMime(["video/webm;codecs=vp8,opus", "video/webm"]) : this._pickMime(["audio/webm;codecs=opus", "audio/webm"]);

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
    this._timerHandle = window.setInterval(() => {
      const elapsed = Math.floor((Date.now() - this._recordStart) / 1000);
      this._setStatus(`Enregistrement… ${elapsed}s`, "busy");
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
    const labelId = kind === "audio" ? "mic-label" : "cam-label";
    const btn = this.shadowRoot.getElementById(btnId);
    const label = this.shadowRoot.getElementById(labelId);
    if (!btn) return;
    btn.classList.toggle("recording", recording);
    if (label) label.textContent = recording ? "Arrêter" : kind === "audio" ? "Message vocal" : "Message vidéo";
    // Disable the other button while recording
    const otherId = kind === "audio" ? "cam-btn" : "mic-btn";
    const other = this.shadowRoot.getElementById(otherId);
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

    if (blob.size === 0) {
      this._setStatus("Enregistrement vide, rien envoyé.", "error");
      return;
    }

    await this._upload(blob, this._recordKind);
  }

  async _upload(blob, kind) {
    this._setStatus("Envoi en cours…", "busy");
    const form = new FormData();
    form.append("alias", this._selectedAlias);
    form.append("kind", kind);
    form.append("file", blob, kind === "audio" ? "clip.webm" : "clip.webm");
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
      this._setStatus("Envoyé ✓", "success");
    } catch (err) {
      this._setStatus(`Échec de l'envoi : ${err.message || err}`, "error");
    }
  }

  disconnectedCallback() {
    if (this._timerHandle) window.clearInterval(this._timerHandle);
    if (this._stream) this._stream.getTracks().forEach((t) => t.stop());
  }
}

customElements.define("simplex-intercom-card", SimplexIntercomCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "simplex-intercom-card",
  name: "SimpleX Intercom",
  description: "Envoyer un message texte, vocal ou vidéo via SimpleX Chat depuis une tablette.",
});
