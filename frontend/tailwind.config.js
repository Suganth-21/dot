/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}", "./public/index.html"],
  theme: {
    extend: {
      colors: {
        clay: {
          bg: "#f4f2ee",
          surface: "#faf9f6",
          card: "#ffffff",
          ink: "#1c1b19",
          muted: "#8a8681",
          line: "#eceae5",
        },
        accent: {
          DEFAULT: "#5b6cff",
          soft: "#e9ebff",
          ink: "#3a48d6",
        },
        mint: { DEFAULT: "#3fbf9a", soft: "#e2f6ef" },
        amber2: { DEFAULT: "#e0a53d", soft: "#fbf1dc" },
        rose2: { DEFAULT: "#e0655b", soft: "#fbe6e3" },
        lilac: { DEFAULT: "#a78bfa", soft: "#efeafd" },
        sky2: { DEFAULT: "#5aa9e6", soft: "#e4f0fb" },
      },
      fontFamily: {
        sans: ["Inter", "SF Pro Display", "-apple-system", "system-ui", "sans-serif"],
      },
      borderRadius: {
        clay: "1.5rem",
        pill: "999px",
      },
      boxShadow: {
        clay: "0 1px 2px rgba(28,27,25,0.04)",
        "clay-hover": "0 8px 30px rgba(28,27,25,0.08)",
        pop: "0 12px 40px rgba(28,27,25,0.12)",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.4s ease forwards",
      },
    },
  },
  plugins: [],
};
