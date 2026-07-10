/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        page: "var(--surface-page)",
        card: "var(--surface-card)",
        subtle: "var(--surface-subtle)",
        muted: "var(--surface-muted)",
        inverse: "var(--surface-inverse)",

        "fg-primary": "var(--text-primary)",
        "fg-default": "var(--text-default)",
        "fg-secondary": "var(--text-secondary)",
        "fg-disabled": "var(--text-disabled)",
        "fg-link": "var(--text-link)",
        "fg-inverse": "var(--text-inverse)",

        "line-subtle": "var(--border-subtle)",
        "line-default": "var(--border-default)",
        "line-muted": "var(--border-muted)",
        "line-focus": "var(--border-focus)",

        ink: "var(--ink)",
        "ink-hover": "var(--ink-hover)",
        "ink-pressed": "var(--ink-pressed)",

        primary: "var(--primary)",
        "primary-hover": "var(--primary-hover)",
        "primary-pressed": "var(--primary-pressed)",
        "primary-fg": "var(--primary-fg)",
        secondary: "var(--secondary)",
        "secondary-hover": "var(--secondary-hover)",

        success: "var(--success)",
        warning: "var(--warning)",
        error: "var(--error)",
        info: "var(--info)",

        "tint-info": "var(--tint-info)",
        "tint-info-strong": "var(--tint-info-strong)",
        "tint-info-border": "var(--tint-info-border)",
        "tint-success": "var(--tint-success)",
        "tint-error": "var(--tint-error)",
        "tint-warning": "var(--tint-warning)",

        "cat-1": "var(--cat-1)",
        "cat-2": "var(--cat-2)",
        "cat-3": "var(--cat-3)",
        "cat-4": "var(--cat-4)",
        "cat-5": "var(--cat-5)",
        "cat-6": "var(--cat-6)",
        "cat-7": "var(--cat-7)",
        "cat-8": "var(--cat-8)",
      },
      borderRadius: {
        sm: "var(--radius-sm)",
        DEFAULT: "var(--radius-sm)",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "monospace"],
      },
      letterSpacing: {
        meta: "0.1em",
        wide2: "0.18em",
      },
      maxWidth: {
        "screen-2xl": "1680px",
      },
    },
  },
  plugins: [],
}
