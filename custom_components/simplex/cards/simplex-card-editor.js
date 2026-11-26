/**
 * SimpleX cards — visual editors (Lovelace "Edit card" UI, no YAML needed).
 *
 * Loaded by the SimpleX Chat integration together with the cards. Each card
 * exposes `static getConfigElement()` returning one of the elements below, built
 * on Home Assistant's own <ha-form> so it follows the user's theme/language.
 */
const SIMPLEX_EDITOR_LABELS = {
  en: {
    alias: ["Contact / group alias", "Leave empty or type “auto” to follow the conversation chosen in the list."],
    title: ["Title", ""],
    history_limit: ["Messages to load", "How many past messages are shown (default 50)."],
    auto_mark_read: ["Mark as read automatically", ""],
    entry_id: ["SimpleX instance", "Only needed if you run several SimpleX integrations."],
    connection_entity: ["Connection sensor", "Defaults to binary_sensor.simplex_chat_connection."],
    navigate_prefix: ["Chat view URL", "Where a click opens the chat, e.g. /simplex-auto-fr/simplex-chat."],
    navigate_mode: ["Navigation mode", "“hash” → /view#alias, “path” → /view/alias."],
    show_search: ["Show the search box", ""],
    aliases: ["Recipients", "Leave empty to use every contact discovered by the integration."],
    default_alias: ["Default recipient", ""],
    hash: "Hash (#alias)",
    path: "Path (/alias)",
  },
  fr: {
    alias: ["Alias du contact / groupe", "Laisser vide ou « auto » pour suivre la conversation choisie dans la liste."],
    title: ["Titre", ""],
    history_limit: ["Messages à charger", "Nombre de messages passés affichés (50 par défaut)."],
    auto_mark_read: ["Marquer comme lu automatiquement", ""],
    entry_id: ["Instance SimpleX", "Utile seulement si vous avez plusieurs intégrations SimpleX."],
    connection_entity: ["Capteur de connexion", "Par défaut : binary_sensor.simplex_chat_connection."],
    navigate_prefix: ["URL de la vue de chat", "Où s'ouvre le chat au clic, ex. /simplex-auto-fr/simplex-chat."],
    navigate_mode: ["Mode de navigation", "« hash » → /vue#alias, « path » → /vue/alias."],
    show_search: ["Afficher la recherche", ""],
    aliases: ["Destinataires", "Laisser vide pour utiliser tous les contacts découverts par l'intégration."],
    default_alias: ["Destinataire par défaut", ""],
    hash: "Hash (#alias)",
    path: "Chemin (/alias)",
  },
};

const _ENTRY = { config_entry: { integration: "simplex" } };
const _CONN = { entity: { domain: "binary_sensor" } };

const SIMPLEX_EDITOR_SCHEMAS = {
  chat: () => [
    { name: "alias", selector: { text: {} } },
    { name: "title", selector: { text: {} } },
    { name: "history_limit", selector: { number: { min: 10, max: 500, step: 10, mode: "box" } } },
    { name: "auto_mark_read", selector: { boolean: {} } },
    { name: "entry_id", selector: _ENTRY },
    { name: "connection_entity", selector: _CONN },
  ],
  conversations: (t) => [
    { name: "title", selector: { text: {} } },
    { name: "navigate_prefix", selector: { text: {} } },
    {
      name: "navigate_mode",
      selector: {
        select: {
          mode: "dropdown",
          options: [
            { value: "hash", label: t.hash },
            { value: "path", label: t.path },
          ],
        },
      },
    },
    { name: "show_search", selector: { boolean: {} } },
    { name: "entry_id", selector: _ENTRY },
  ],
  intercom: () => [
    { name: "title", selector: { text: {} } },
    { name: "aliases", selector: { text: { multiple: true } } },
    { name: "default_alias", selector: { text: {} } },
    { name: "entry_id", selector: _ENTRY },
    { name: "connection_entity", selector: _CONN },
  ],
};

// What the card assumes when a key is absent: shown in the form, not persisted.
const SIMPLEX_EDITOR_DEFAULTS = {
  chat: { alias: "auto", history_limit: 50, auto_mark_read: true },
  conversations: { navigate_mode: "hash", show_search: true },
  intercom: {},
};

class SimplexCardEditor extends HTMLElement {
  constructor(kind) {
    super();
    this._kind = kind;
    this._hass = null;
    this._config = {};
    this._form = null;
  }

  set hass(hass) {
    this._hass = hass;
    this._sync();
  }

  setConfig(config) {
    this._config = { ...config };
    this._sync();
  }

  _labels() {
    const lang = ((this._hass && this._hass.language) || "en").slice(0, 2);
    return SIMPLEX_EDITOR_LABELS[lang] || SIMPLEX_EDITOR_LABELS.en;
  }

  _sync() {
    if (!this._hass) return;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.addEventListener("value-changed", (ev) => this._changed(ev));
      this.appendChild(this._form);
    }
    const t = this._labels();
    this._form.hass = this._hass;
    this._form.data = { ...SIMPLEX_EDITOR_DEFAULTS[this._kind], ...this._config };
    this._form.schema = SIMPLEX_EDITOR_SCHEMAS[this._kind](t);
    this._form.computeLabel = (s) => (t[s.name] ? t[s.name][0] : s.name);
    this._form.computeHelper = (s) => (t[s.name] ? t[s.name][1] : "");
  }

  _changed(ev) {
    ev.stopPropagation();
    const defaults = SIMPLEX_EDITOR_DEFAULTS[this._kind];
    const config = { type: this._config.type };
    for (const [key, value] of Object.entries(ev.detail.value || {})) {
      const empty = value === "" || value === undefined || value === null || (Array.isArray(value) && !value.length);
      // Keep the YAML minimal: drop empties and values equal to the default.
      if (empty || (key in defaults && defaults[key] === value && !(key in this._config))) continue;
      config[key] = value;
    }
    this._config = config;
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }));
  }
}

for (const kind of ["chat", "conversations", "intercom"]) {
  const tag = `simplex-${kind}-card-editor`;
  if (!customElements.get(tag)) {
    customElements.define(tag, class extends SimplexCardEditor { constructor() { super(kind); } });
  }
}
