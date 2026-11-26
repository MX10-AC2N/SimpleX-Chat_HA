/**
 * SimpleX Messenger — a Glass, responsive "messenger" shell.
 *
 * It does not reimplement the chat: it hosts the two existing cards
 * (`simplex-conversations-card` + `simplex-chat-card`) side by side on desktop
 * and as a list → conversation flow on mobile, and themes them through their
 * `--simplex-*` CSS variables.
 *
 * Contract with the hosted cards (see their sources):
 *  - the conversations card, on click, stores the alias in
 *    sessionStorage["simplex_chat_alias"], then does
 *    history.pushState(null, "", `${navigate_prefix}#${alias}`) + popstate;
 *  - the chat card (alias: auto) follows hash / popstate / location-changed.
 * Hence `navigate_prefix` MUST be the path of the view hosting this card,
 * otherwise a click navigates away and Home Assistant unmounts everything.
 */
import { LitElement, css, html, nothing } from "lit";
import { glassTokens } from "./glass-theme";
import type {
  GlassIntensity,
  HomeAssistant,
  LovelaceCard,
  SimplexMessengerConfig,
} from "./types";

const CARD_TAG = "simplex-messenger-card";
const ALIAS_STORAGE_KEY = "simplex_chat_alias"; // written by the conversations card
const CARDS_TIMEOUT_MS = 8000;
const ROUTE_EVENTS = ["hashchange", "popstate", "location-changed"] as const;

const STRINGS = {
  en: {
    inbox: "Conversations",
    subtitle: "Private messenger",
    pill: "Private communication",
    pick: "Select a conversation",
    pickSub: "Choose a contact or a group in the list.",
    back: "Back to conversations",
    loading: "Loading SimpleX…",
    missing:
      "The SimpleX cards are not loaded. Restart Home Assistant, then reload this page (Ctrl+F5).",
  },
  fr: {
    inbox: "Conversations",
    subtitle: "Messagerie privée",
    pill: "Communication privée",
    pick: "Sélectionnez une conversation",
    pickSub: "Choisissez un contact ou un groupe dans la liste.",
    back: "Retour aux conversations",
    loading: "Chargement de SimpleX…",
    missing:
      "Les cartes SimpleX ne sont pas chargées. Redémarrez Home Assistant puis rechargez la page (Ctrl+F5).",
  },
} as const;

type Strings = Record<keyof (typeof STRINGS)["en"], string>;
type CardState = "loading" | "ready" | "missing";

class SimplexMessengerCard extends LitElement {
  static properties = {
    hass: { attribute: false },
    _config: { state: true },
    _chatOpen: { state: true },
    _hasAlias: { state: true },
    _cards: { state: true },
  };

  static styles = [
    glassTokens,
    css`
      :host {
        width: 100%;
        min-width: 0;
      }

      .shell {
        position: relative;
        isolation: isolate;
        display: flex;
        flex-direction: column;
        width: 100%;
        min-height: 520px;
        height: min(860px, calc(100vh - 148px));
        overflow: hidden;
        border: 1px solid var(--sx-glass-border);
        border-radius: var(--sx-glass-radius);
        background:
          radial-gradient(ellipse at 8% 0%, rgba(73, 170, 159, 0.17), transparent 36%),
          radial-gradient(ellipse at 92% 100%, rgba(99, 125, 202, 0.13), transparent 38%),
          var(--sx-glass-bg);
        box-shadow:
          0 24px 70px rgba(0, 0, 0, 0.28),
          inset 0 1px 0 var(--sx-glass-highlight);
        backdrop-filter: blur(var(--sx-glass-blur)) saturate(145%);
        -webkit-backdrop-filter: blur(var(--sx-glass-blur)) saturate(145%);
      }

      :host([glass-intensity="off"]) .shell {
        backdrop-filter: none;
        -webkit-backdrop-filter: none;
        box-shadow: none;
      }

      .topbar {
        flex: 0 0 auto;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        min-height: 64px;
        padding: 10px 20px;
        border-bottom: 1px solid var(--sx-glass-border);
        background: rgba(255, 255, 255, 0.025);
      }

      .brand {
        display: flex;
        align-items: center;
        gap: 12px;
        min-width: 0;
      }

      .brand-mark {
        display: grid;
        width: 38px;
        height: 38px;
        place-items: center;
        border: 1px solid rgba(112, 224, 189, 0.28);
        border-radius: 13px;
        color: var(--sx-glass-accent);
        background: linear-gradient(145deg, rgba(112, 224, 189, 0.18), rgba(112, 224, 189, 0.045));
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.13);
      }

      .brand-mark svg {
        width: 21px;
        height: 21px;
      }

      .brand-copy {
        display: grid;
        gap: 2px;
        min-width: 0;
      }

      .brand-name {
        font-size: 15px;
        line-height: 1.15;
        font-weight: 720;
        letter-spacing: -0.025em;
      }

      .brand-subtitle {
        color: var(--sx-glass-muted);
        font-size: 10px;
        line-height: 1;
        letter-spacing: 0.15em;
        text-transform: uppercase;
      }

      .privacy-pill {
        display: inline-flex;
        align-items: center;
        gap: 7px;
        padding: 7px 10px;
        border: 1px solid rgba(112, 224, 189, 0.17);
        border-radius: 999px;
        background: rgba(112, 224, 189, 0.065);
        color: #b9f4df;
        font-size: 12px;
        white-space: nowrap;
      }

      .privacy-pill svg {
        width: 13px;
        height: 13px;
      }

      .workspace {
        position: relative;
        flex: 1 1 auto;
        display: grid;
        grid-template-columns: minmax(270px, 340px) minmax(0, 1fr);
        min-height: 0;
        overflow: hidden;
      }

      .inbox,
      .thread {
        position: relative;
        min-width: 0;
        min-height: 0;
      }

      .inbox {
        overflow-y: auto;
        border-right: 1px solid var(--sx-glass-border);
        background: rgba(255, 255, 255, 0.018);
        scrollbar-width: thin;
      }

      .thread {
        display: flex;
        flex-direction: column;
        overflow: hidden;
        background: rgba(8, 14, 20, 0.16);
      }

      /* Theme the hosted cards through their public CSS variables. */
      simplex-conversations-card,
      simplex-chat-card {
        display: block;
        --simplex-bg: transparent;
        --ha-card-background: transparent;
        --ha-card-box-shadow: none;
        --ha-card-border-width: 0;
        --ha-card-border-radius: 0;
        --ha-card-border-color: transparent;
      }

      simplex-chat-card {
        flex: 1 1 auto;
        min-height: 0;
        width: 100%;
        --simplex-card-height: 100%;
        --simplex-header-bg: rgba(255, 255, 255, 0.045);
        --simplex-bubble-in: rgba(255, 255, 255, 0.1);
        --simplex-bubble-out: rgba(56, 201, 155, 0.78);
      }

      .mobile-bar {
        display: none;
      }

      .placeholder,
      .overlay {
        position: absolute;
        inset: 0;
        z-index: 3;
        display: grid;
        place-items: center;
        padding: 24px;
        color: var(--sx-glass-muted);
        text-align: center;
        font-size: 13px;
      }

      .placeholder {
        pointer-events: none;
        background: rgba(8, 14, 20, 0.35);
      }

      .overlay {
        background: rgba(8, 14, 20, 0.55);
      }

      .placeholder strong {
        display: block;
        margin-bottom: 6px;
        color: var(--sx-glass-text);
        font-size: 15px;
        font-weight: 650;
      }

      .spinner {
        width: 30px;
        height: 30px;
        margin: 0 auto 12px;
        border: 2px solid rgba(112, 224, 189, 0.18);
        border-top-color: var(--sx-glass-accent);
        border-radius: 50%;
        animation: spin 0.9s linear infinite;
      }

      @keyframes spin {
        to {
          transform: rotate(360deg);
        }
      }

      @media (max-width: 760px) {
        .shell {
          height: calc(100dvh - 112px);
          min-height: 480px;
          border-radius: 16px;
        }

        .topbar {
          min-height: 56px;
          padding: 8px 13px;
        }

        .brand-mark {
          width: 34px;
          height: 34px;
          border-radius: 11px;
        }

        .privacy-pill {
          padding: 6px 8px;
          font-size: 10px;
        }

        .workspace {
          display: block;
        }

        .inbox,
        .thread {
          position: absolute;
          inset: 0;
          border: 0;
        }

        .thread {
          display: none;
        }

        .shell.chat-open .inbox {
          display: none;
        }

        .shell.chat-open .thread {
          display: flex;
        }

        /* Full-screen conversation: the brand bar makes room. */
        .shell.chat-open .topbar {
          display: none;
        }

        .mobile-bar {
          flex: 0 0 auto;
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 6px 8px;
          border-bottom: 1px solid var(--sx-glass-border);
          background: rgba(255, 255, 255, 0.025);
        }

        .mobile-back {
          display: inline-flex;
          align-items: center;
          gap: 4px;
          padding: 6px 12px 6px 8px;
          border: 1px solid var(--sx-glass-border);
          border-radius: 12px;
          color: var(--sx-glass-text);
          background: rgba(18, 27, 36, 0.6);
          font-size: 13px;
          cursor: pointer;
        }

        .mobile-back svg {
          width: 16px;
          height: 16px;
        }

        .placeholder {
          display: none;
        }
      }

      @media (max-width: 420px) {
        .shell {
          height: calc(100dvh - 96px);
          border-radius: 12px;
        }

        .brand-subtitle {
          display: none;
        }
      }
    `,
  ];

  hass?: HomeAssistant;
  private _config?: SimplexMessengerConfig;
  private _chatOpen = false;
  private _hasAlias = false;
  private _cards: CardState = "loading";
  private _configuredPrefix: string | null = null;
  private _watchdog?: number;
  private _onRoute = () => this._syncRoute();

  setConfig(config: SimplexMessengerConfig): void {
    if (!config) throw new Error("SimpleX Messenger: invalid configuration.");
    this._config = {
      navigate_mode: "hash",
      show_branding: true,
      show_search: true,
      glass_intensity: "balanced",
      ...config,
    };
    this.setAttribute("glass-intensity", this._config.glass_intensity ?? "balanced");
    this._syncRoute();
    // Re-apply to already-created children (editor changes, YAML edits).
    if (this.hasUpdated && this._cards === "ready") this._configureChildren();
  }

  connectedCallback(): void {
    super.connectedCallback();
    for (const ev of ROUTE_EVENTS) window.addEventListener(ev, this._onRoute);
    this._syncRoute();
  }

  disconnectedCallback(): void {
    for (const ev of ROUTE_EVENTS) window.removeEventListener(ev, this._onRoute);
    window.clearTimeout(this._watchdog);
    super.disconnectedCallback();
  }

  protected firstUpdated(): void {
    void this._waitForCards();
  }

  protected updated(changed: Map<string, unknown>): void {
    if (changed.has("hass")) this._pushHass();
  }

  // ---- route -------------------------------------------------------------

  private get _t(): Strings {
    const lang = (this.hass?.language ?? "en").slice(0, 2);
    return lang === "fr" ? STRINGS.fr : STRINGS.en;
  }

  private _syncRoute(): void {
    const hash = window.location.hash.replace(/^#/, "").trim();
    // Mobile shows the conversation only when the URL carries one.
    this._chatOpen = hash.length > 0;
    // Desktop: the chat card also falls back to the alias the list stored.
    let hasAlias = this._chatOpen;
    if (!hasAlias) {
      try {
        hasAlias = Boolean(window.sessionStorage.getItem(ALIAS_STORAGE_KEY));
      } catch {
        /* private mode: the hash is the only carrier */
      }
    }
    this._hasAlias = hasAlias;
    // The chat card reads the alias on its first `hass`: hand it over only once
    // the URL carries one, otherwise it falls back to the last path segment
    // (the view name) and requests a conversation that does not exist.
    this._pushHass();

    // The view may be routed after setConfig(): keep the prefix in step.
    if (this._cards === "ready" && !this._config?.navigate_prefix) {
      if (this._configuredPrefix !== this._viewPath()) this._configureChildren();
    }
  }

  private _viewPath(): string {
    return window.location.pathname.replace(/\/+$/, "") || "/";
  }

  private _goBack(): void {
    const url = new URL(window.location.href);
    url.hash = "";
    window.history.replaceState(null, "", url);
    this._syncRoute();
  }

  // ---- hosted cards ------------------------------------------------------

  private _card<T extends LovelaceCard>(tag: string): T | null {
    return this.renderRoot.querySelector(tag) as T | null;
  }

  private async _waitForCards(): Promise<void> {
    const defined = Promise.all([
      customElements.whenDefined("simplex-conversations-card"),
      customElements.whenDefined("simplex-chat-card"),
    ]).then(() => true);
    const timeout = new Promise<boolean>((resolve) => {
      this._watchdog = window.setTimeout(() => resolve(false), CARDS_TIMEOUT_MS);
    });
    const ok = await Promise.race([defined, timeout]);
    window.clearTimeout(this._watchdog);
    if (!ok) {
      this._cards = "missing";
      return;
    }
    // Each card requires setConfig() before its first `hass`.
    this._configureChildren();
    this._cards = "ready";
    this._pushHass();
  }

  private _configureChildren(): void {
    const cfg = this._config;
    const inbox = this._card("simplex-conversations-card");
    const chat = this._card("simplex-chat-card");
    if (!cfg || !inbox || !chat) return;

    const prefix = cfg.navigate_prefix || this._viewPath();
    this._configuredPrefix = cfg.navigate_prefix ? null : prefix;

    const entry = cfg.entry_id ? { entry_id: cfg.entry_id } : {};
    inbox.setConfig({
      title: cfg.title || this._t.inbox,
      navigate_prefix: prefix,
      navigate_mode: cfg.navigate_mode ?? "hash",
      show_search: cfg.show_search !== false,
      ...entry,
    });
    chat.setConfig({
      alias: "auto",
      ...(cfg.history_limit ? { history_limit: cfg.history_limit } : {}),
      ...(cfg.auto_mark_read === false ? { auto_mark_read: false } : {}),
      ...(cfg.connection_entity ? { connection_entity: cfg.connection_entity } : {}),
      ...entry,
    });
    this._pushHass();
  }

  private _pushHass(): void {
    if (this._cards !== "ready" || !this.hass) return;
    const inbox = this._card("simplex-conversations-card");
    const chat = this._card("simplex-chat-card");
    if (inbox) inbox.hass = this.hass;
    if (chat && this._hasAlias) chat.hass = this.hass;
  }

  // ---- Lovelace card API -------------------------------------------------

  getCardSize(): number {
    return 8;
  }

  getGridOptions() {
    return { columns: 12, rows: 8, min_columns: 6, min_rows: 5 };
  }

  static getConfigElement(): HTMLElement {
    return document.createElement("simplex-messenger-card-editor");
  }

  static getStubConfig(): Partial<SimplexMessengerConfig> {
    return { show_branding: true, glass_intensity: "balanced" as GlassIntensity };
  }

  // ---- render ------------------------------------------------------------

  private _renderTopbar(t: Strings) {
    return html`
      <header class="topbar">
        <div class="brand">
          <div class="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none">
              <path
                d="M4.5 6.8A3.3 3.3 0 0 1 7.8 3.5h8.4a3.3 3.3 0 0 1 3.3 3.3v6.4a3.3 3.3 0 0 1-3.3 3.3h-4.4l-4.6 3.2v-3.2h-.1a3.3 3.3 0 0 1-2.6-3.3V6.8Z"
                stroke="currentColor"
                stroke-width="1.6"
                stroke-linejoin="round"
              />
              <path d="M8 8.8h8M8 12h5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
            </svg>
          </div>
          <div class="brand-copy">
            <span class="brand-name">SimpleX</span>
            <span class="brand-subtitle">${t.subtitle}</span>
          </div>
        </div>
        <span class="privacy-pill">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path
              d="M7 10V7a5 5 0 0 1 10 0v3m-11 0h12v10H6V10Z"
              stroke="currentColor"
              stroke-width="1.7"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
          ${t.pill}
        </span>
      </header>
    `;
  }

  render() {
    if (!this._config) return nothing;
    const t = this._t;

    return html`
      <section class="shell ${this._chatOpen ? "chat-open" : ""}" aria-label="SimpleX Messenger">
        ${this._config.show_branding !== false ? this._renderTopbar(t) : nothing}

        <div class="workspace">
          <aside class="inbox" aria-label=${t.inbox}>
            <simplex-conversations-card></simplex-conversations-card>
          </aside>

          <main class="thread">
            <div class="mobile-bar">
              <button class="mobile-back" @click=${this._goBack} aria-label=${t.back}>
                <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path
                    d="m14.5 5-7 7 7 7"
                    stroke="currentColor"
                    stroke-width="2"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  />
                </svg>
                ${t.inbox}
              </button>
            </div>
            <simplex-chat-card></simplex-chat-card>
            ${!this._hasAlias && this._cards === "ready"
              ? html`<div class="placeholder">
                  <div><strong>${t.pick}</strong>${t.pickSub}</div>
                </div>`
              : nothing}
          </main>

          ${this._cards !== "ready"
            ? html`<div class="overlay" role="status">
                <div>
                  ${this._cards === "loading" ? html`<div class="spinner"></div>` : nothing}
                  ${this._cards === "loading" ? t.loading : t.missing}
                </div>
              </div>`
            : nothing}
        </div>
      </section>
    `;
  }
}

if (!customElements.get(CARD_TAG)) {
  customElements.define(CARD_TAG, SimplexMessengerCard);
}

const w = window as Window & { customCards?: Array<Record<string, unknown>> };
w.customCards = w.customCards || [];
w.customCards.push({
  type: CARD_TAG,
  name: "SimpleX Messenger",
  description: "Glass messenger: conversation list and chat in one responsive view.",
  preview: false,
});
