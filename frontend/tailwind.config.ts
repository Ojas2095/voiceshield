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
        "surface-low": c("--c-surface-low"),
        "surface-high": c("--c-surface-high"),
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
        sans: ["var(--font-inter)", "ui-sans-serif", "system-ui", "Segoe UI", "Roboto", "Arial", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
      fontSize: {
        // Stitch scale — dense, engineered.
        "label-caps": ["0.6875rem", { lineHeight: "0.875rem", letterSpacing: "0.06em", fontWeight: "700" }],
        "data": ["0.75rem", { lineHeight: "1.125rem", letterSpacing: "-0.01em" }],
        "data-sm": ["0.6875rem", { lineHeight: "1rem" }],
        "body-sm": ["0.8125rem", { lineHeight: "1.25rem" }],
        "metric": ["1.5rem", { lineHeight: "1.75rem", letterSpacing: "-0.03em", fontWeight: "600" }],
      },
      borderRadius: { DEFAULT: "4px", sm: "2px", md: "4px", lg: "6px" },
    },
  },
  plugins: [],
};
export default config;
