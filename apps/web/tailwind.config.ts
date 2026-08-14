import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        canvas: "var(--canvas)",
        surface: {
          DEFAULT: "var(--surface)",
          raised: "var(--surface-raised)",
          sunken: "var(--surface-sunken)",
        },
        line: {
          DEFAULT: "var(--line)",
          strong: "var(--line-strong)",
        },
        content: {
          DEFAULT: "var(--text)",
          secondary: "var(--text-secondary)",
          muted: "var(--text-muted)",
        },
        accent: {
          DEFAULT: "var(--accent)",
          hover: "var(--accent-hover)",
          text: "var(--accent-text)",
          on: "var(--accent-on)",
        },
        paid: { DEFAULT: "var(--paid)", tint: "var(--paid-tint)" },
        pending: { DEFAULT: "var(--pending)", tint: "var(--pending-tint)" },
        overdue: { DEFAULT: "var(--overdue)", tint: "var(--overdue-tint)" },
        neutral: { DEFAULT: "var(--neutral)", tint: "var(--neutral-tint)" },
        disputed: { DEFAULT: "var(--disputed)", tint: "var(--disputed-tint)" },
        chain: { DEFAULT: "var(--chain)", tint: "var(--chain-tint)" },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      borderRadius: {
        DEFAULT: "var(--radius)",
        sm: "0.375rem",
        md: "var(--radius)",
        lg: "var(--radius)",
      },
      boxShadow: {
        card: "var(--shadow-card)",
        lifted: "var(--shadow-lifted)",
      },
      transitionTimingFunction: {
        out: "var(--ease-out)",
      },
    },
  },
  plugins: [],
};
export default config;
