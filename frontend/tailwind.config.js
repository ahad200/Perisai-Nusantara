/** @type {import('tailwindcss').Config} */
// Token dirujuk dari CSS variables (lihat src/style.css) agar tema gelap/terang
// bisa ditukar tanpa mengubah kelas. Sesuai PRD Lampiran C.2.
export default {
  content: ["./index.html", "./src/**/*.{vue,ts}"],
  theme: {
    // Skala ukuran terbatas (C.2): 12/13/14/16/20/24.
    fontSize: {
      xs: ["12px", "16px"],
      sm: ["13px", "18px"],
      base: ["14px", "20px"],
      lg: ["16px", "24px"],
      xl: ["20px", "28px"],
      "2xl": ["24px", "32px"],
    },
    extend: {
      colors: {
        graphite: {
          base: "var(--bg-base)",
          surface: "var(--bg-surface)",
          raised: "var(--bg-raised)",
        },
        edge: "var(--border)",
        ink: {
          DEFAULT: "var(--text)",
          muted: "var(--text-muted)",
          dim: "var(--text-dim)",
        },
        accent: { DEFAULT: "var(--accent)", ink: "var(--accent-ink)" },
        data2: "var(--data-2)",
        sev: {
          critical: "var(--sev-critical)",
          high: "var(--sev-high)",
          medium: "var(--sev-medium)",
          low: "var(--sev-low)",
          info: "var(--sev-info)",
        },
      },
      fontFamily: {
        sans: ["IBM Plex Sans", "system-ui", "sans-serif"],
        mono: ["IBM Plex Mono", "ui-monospace", "monospace"],
      },
      // Radius kecil (C.2): 2–4px.
      borderRadius: { sm: "2px", DEFAULT: "3px", md: "4px" },
      fontVariantNumeric: { tabular: "tabular-nums" },
    },
  },
  plugins: [],
};
