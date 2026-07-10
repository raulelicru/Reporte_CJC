import type { Config } from "tailwindcss";

/**
 * Identidad visual §9 — tema claro, editorial, sobrio.
 * Tokens tomados del reporte HTML de referencia; no inventar colores nuevos.
 */
const config: Config = {
  content: [
    "./src/app/**/*.{ts,tsx}",
    "./src/components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: "#FBFAF7",
        panel: "#FFFFFF",
        ink: "#16202E",
        ink70: "#5A6472",
        line: "#E4E8EE",
        amber: "#B77E17", // Llamada
        teal: "#12A99A", // SMS
        rose: "#D6486A", // IVR
        grayc: "#8A94A3", // Espontáneo
      },
      fontFamily: {
        display: ["Fraunces", "Georgia", "serif"],
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "monospace"],
      },
      borderRadius: {
        card: "10px",
      },
      boxShadow: {
        card: "0 1px 2px rgba(22,32,46,0.04), 0 1px 1px rgba(22,32,46,0.03)",
      },
    },
  },
  plugins: [],
};

export default config;
