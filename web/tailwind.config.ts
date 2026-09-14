import type { Config } from "tailwindcss";

// Every colour here is a token from app/globals.css, which is in turn a colour the map draws
// with. Components should reach for `text-oil` / `border-line` / `bg-hull`, never a raw hex —
// that is what keeps the panel and the map speaking the same language.
const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--abyss)",
        foreground: "var(--ink)",

        // Channel form, so an opacity modifier (`bg-overlay/90`, `border-drift/45`) actually
        // compiles. Handing Tailwind a finished `var(--overlay)` makes it drop the rule
        // silently, which reads as a transparent panel rather than as a build error.
        abyss: "rgb(var(--abyss-rgb) / <alpha-value>)",
        deep: "rgb(var(--deep-rgb) / <alpha-value>)",
        hull: "rgb(var(--hull-rgb) / <alpha-value>)",
        raised: "rgb(var(--raised-rgb) / <alpha-value>)",
        overlay: "rgb(var(--overlay-rgb) / <alpha-value>)",

        // Hairlines are already rgba and are never used with a modifier.
        line: "var(--line)",
        "line-strong": "var(--line-strong)",

        ink: "rgb(var(--ink-rgb) / <alpha-value>)",
        "ink-2": "rgb(var(--ink-2-rgb) / <alpha-value>)",
        "ink-3": "rgb(var(--ink-3-rgb) / <alpha-value>)",
        "ink-4": "rgb(var(--ink-4-rgb) / <alpha-value>)",

        drift: "rgb(var(--drift-rgb) / <alpha-value>)",
        oil: "rgb(var(--oil-rgb) / <alpha-value>)",
        contact: "rgb(var(--contact-rgb) / <alpha-value>)",
        infra: "rgb(var(--infra-rgb) / <alpha-value>)",
        reject: "rgb(var(--reject-rgb) / <alpha-value>)",
        alert: "rgb(var(--alert-rgb) / <alpha-value>)",
      },
      fontFamily: {
        sans: ["var(--font-ui)"],
        mono: ["var(--font-data)"],
      },
      transitionTimingFunction: {
        out: "var(--ease-out)",
        "in-out": "var(--ease-in-out)",
      },
    },
  },
  plugins: [],
};
export default config;
