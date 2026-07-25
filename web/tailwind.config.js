/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        surface: {
          DEFAULT: "hsl(var(--surface))",
          foreground: "hsl(var(--surface-foreground))",
          elevated: "hsl(var(--surface-elevated))",
          subtle: "hsl(var(--surface-subtle))",
        },
        brand: {
          ink: "hsl(var(--brand-ink))",
          paper: "hsl(var(--brand-paper))",
          sandstone: "hsl(var(--brand-sandstone))",
          brass: "hsl(var(--brand-brass))",
          "brass-foreground": "hsl(var(--brand-brass-foreground))",
        },
        status: {
          todo: {
            DEFAULT: "hsl(var(--status-todo))",
            foreground: "hsl(var(--status-todo-foreground))",
            border: "hsl(var(--status-todo-border))",
          },
          progress: {
            DEFAULT: "hsl(var(--status-progress))",
            foreground: "hsl(var(--status-progress-foreground))",
            border: "hsl(var(--status-progress-border))",
          },
          blocked: {
            DEFAULT: "hsl(var(--status-blocked))",
            foreground: "hsl(var(--status-blocked-foreground))",
            border: "hsl(var(--status-blocked-border))",
          },
          review: {
            DEFAULT: "hsl(var(--status-review))",
            foreground: "hsl(var(--status-review-foreground))",
            border: "hsl(var(--status-review-border))",
          },
          done: {
            DEFAULT: "hsl(var(--status-done))",
            foreground: "hsl(var(--status-done-foreground))",
            border: "hsl(var(--status-done-border))",
          },
        },
        actor: {
          human: {
            DEFAULT: "hsl(var(--actor-human))",
            foreground: "hsl(var(--actor-human-foreground))",
            border: "hsl(var(--actor-human-border))",
          },
          agent: {
            DEFAULT: "hsl(var(--actor-agent))",
            foreground: "hsl(var(--actor-agent-foreground))",
            border: "hsl(var(--actor-agent-border))",
          },
          unassigned: {
            DEFAULT: "hsl(var(--actor-unassigned))",
            foreground: "hsl(var(--actor-unassigned-foreground))",
            border: "hsl(var(--actor-unassigned-border))",
          },
        },
        success: {
          DEFAULT: "hsl(var(--success))",
          foreground: "hsl(var(--success-foreground))",
        },
        warning: {
          DEFAULT: "hsl(var(--warning))",
          foreground: "hsl(var(--warning-foreground))",
        },
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      fontFamily: {
        sans: [
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          '"Segoe UI"',
          "sans-serif",
        ],
        mono: [
          '"SFMono-Regular"',
          "Consolas",
          '"Liberation Mono"',
          "Menlo",
          "monospace",
        ],
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        "mouvadah-enter": {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "mouvadah-trace": {
          from: { strokeDashoffset: "1" },
          to: { strokeDashoffset: "0" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        shimmer: "shimmer 2s linear infinite",
        "mouvadah-enter":
          "mouvadah-enter var(--motion-duration-slow) var(--motion-ease-standard) both",
        "mouvadah-trace":
          "mouvadah-trace var(--motion-duration-trace) var(--motion-ease-standard) both",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
