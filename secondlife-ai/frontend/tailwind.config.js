/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ['"Bricolage Grotesque"', "ui-sans-serif", "system-ui", "sans-serif"],
        sans: ['"IBM Plex Sans"', "ui-sans-serif", "system-ui", "sans-serif"],
      },
      colors: {
        // PCB-green and cool grey-green replace Tailwind's emerald/stone so every existing page picks them up.
        emerald: {
          50: "#E8F3EE", 100: "#D0E6DC", 200: "#A5CDB9", 300: "#74B096", 400: "#438F72",
          500: "#1F7459", 600: "#0E5A43", 700: "#0B4A37", 800: "#083A2B", 900: "#052A20",
        },
        stone: {
          50: "#F4F6F4", 100: "#E9EDE9", 200: "#D9DFD9", 300: "#C2CAC3", 400: "#97A29A",
          500: "#6C7A71", 600: "#52615A", 700: "#3C4A43", 800: "#27342E", 900: "#14201B",
        },
        ink: "#0D2A22",       // sidebar / dark band
        gold: { DEFAULT: "#B8892B", soft: "#F3E7C4" }, // gold-plated pads: the single accent
        slate2: "#3C6E8F",
      },
      keyframes: {
        rise: { from: { opacity: 0, transform: "translateY(8px)" }, to: { opacity: 1, transform: "none" } },
        pulseRing: { "0%": { boxShadow: "0 0 0 0 rgba(184,137,43,.45)" }, "100%": { boxShadow: "0 0 0 14px rgba(184,137,43,0)" } },
      },
      animation: { rise: "rise .25s ease-out", pulseRing: "pulseRing 1.4s ease-out infinite" },
    },
  },
  plugins: [],
};
