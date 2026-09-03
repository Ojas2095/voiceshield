import type { Config } from "tailwindcss";

/**
 * VoiceShield design system — a restrained fraud-monitoring console.
 * Colours are CSS variables (R G B triplets) so the same tokens work in light
 * and dark themes (see globals.css). `<alpha-value>` keeps opacity utilities
 * like `bg-brand/70` working.
 */
const c = (v: string) => `rgb(var(${v}) / <alpha-value>)`;

const config: Config = {
  darkMode: "class",
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./hooks/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        canvas: c("--c-canvas"),
        surface: c("--c-surface"),
        line: c("--c-line"),
        navy: c("--c-navy"),
        ink: c("--c-ink"),
        muted: c("--c-muted"),
        brand: c("--c-brand"),
        "brand-dark": c("--c-brand-dark"),
        "brand-soft": c("--c-brand-soft"),
        evidence: c("--c-evidence"),
        "evidence-soft": c("--c-evidence-soft"),
        risk: {
          low: c("--c-risk-low"),
          med: c("--c-risk-med"),
          high: c("--c-risk-high"),
        },
        "low-soft": c("--c-low-soft"),
        "low-line": c("--c-low-line"),
        "med-soft": c("--c-med-soft"),
        "med-line": c("--c-med-line"),
        "high-soft": c("--c-high-soft"),
        "high-line": c("--c-high-line"),
      },
      fontFamily: {
        sans: ["ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "Arial", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(15,37,64,0.04), 0 1px 3px rgba(15,37,64,0.06)",
      },
      borderRadius: { md: "6px", lg: "8px" },
    },
  },
  plugins: [],
};
export default config;
