export interface HomeAssistant {
  language?: string;
  states?: Record<string, unknown>;
  [key: string]: unknown;
}

export type GlassIntensity = "off" | "subtle" | "balanced" | "strong";

/** Options of `custom:simplex-messenger-card`. */
export interface SimplexMessengerConfig {
  type: string;
  /** Inbox header title (default: localised "Conversations"). */
  title?: string;
  /**
   * Path of the view hosting this card, e.g. /simplex-messenger-fr/messenger.
   * Leave empty: it is detected from the current URL.
   */
  navigate_prefix?: string;
  navigate_mode?: "hash" | "path";
  show_branding?: boolean;
  show_search?: boolean;
  glass_intensity?: GlassIntensity;
  // Forwarded as-is to the SimpleX cards.
  history_limit?: number;
  auto_mark_read?: boolean;
  entry_id?: string;
  connection_entity?: string;
}

/** The two existing cards, driven through the standard Lovelace card API. */
export interface LovelaceCard extends HTMLElement {
  hass?: HomeAssistant;
  setConfig(config: Record<string, unknown>): void;
}
