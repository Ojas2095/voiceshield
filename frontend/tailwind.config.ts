import type { Config } from "tailwindcss";

/**
 * VoiceShield design system — a restrained fraud-monitoring console.
 * Light neutral canvas, navy typography, one restrained brand blue, and
 * colour used ONLY to communicate risk (green/amber/red) and evidence (purple).
 */
const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        canvas: "#f3f5f8",   // page background
        surface: "#ffffff",  // cards / panels
        line: "#e3e7ee",     // hairline borders
        navy: "#0f2540",     // headings / primary text
        ink: "#1f2a37",      // body text
        muted: "#6b7580",    // secondary text
        brand: "#2563a8",    // restrained blue (actions, links, accents)
        "brand-dark": "#1d4e85",
        risk: {
          low: "#1a7f4b",    // green — authentic / low
          med: "#b7791f",    // amber — suspicious / medium
          high: "#c0392b",   // red — fraud / high
        },
        evidence: "#6b3fa0", // purple — reserved for the evidence chain
      },
      fontFamily: {
        sans: ["ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "Arial", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(15,37,64,0.04), 0 1px 3px rgba(15,37,64,0.06)",
        raise: "0 4px 12px rgba(15,37,64,0.08)",
      },
      borderRadius: {
        md: "6px",
        lg: "8px",
      },
    },
  },
  plugins: [],
};
export default config;
