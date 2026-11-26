import { css } from "lit";

/**
 * Glass design tokens. Independent of the Home Assistant theme on purpose:
 * the SimpleX cards are dark by design.
 */
export const glassTokens = css`
  :host {
    --sx-glass-bg: rgba(15, 22, 30, 0.76);
    --sx-glass-border: rgba(219, 237, 248, 0.12);
    --sx-glass-highlight: rgba(255, 255, 255, 0.09);
    --sx-glass-text: #f3f7fa;
    --sx-glass-muted: #9eacb9;
    --sx-glass-accent: #70e0bd;
    --sx-glass-accent-strong: #38c99b;
    --sx-glass-radius: 22px;
    --sx-glass-blur: 22px;

    color: var(--sx-glass-text);
    color-scheme: dark;
    display: block;
    font-family: Inter, ui-sans-serif, system-ui, -apple-system,
      BlinkMacSystemFont, "Segoe UI", sans-serif;
  }

  :host([glass-intensity="subtle"]) {
    --sx-glass-bg: rgba(15, 22, 30, 0.9);
    --sx-glass-blur: 12px;
  }

  :host([glass-intensity="strong"]) {
    --sx-glass-bg: rgba(15, 22, 30, 0.62);
    --sx-glass-blur: 30px;
  }

  /* No blur at all (wall tablets, old phones): solid background. */
  :host([glass-intensity="off"]) {
    --sx-glass-bg: #0e151c;
    --sx-glass-blur: 0px;
  }

  * {
    box-sizing: border-box;
  }

  button {
    font: inherit;
  }

  button:focus-visible {
    outline: 2px solid var(--sx-glass-accent);
    outline-offset: 3px;
  }

  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
      animation-duration: 0.01ms !important;
      transition-duration: 0.01ms !important;
    }
  }
`;
