import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        ink: "rgb(var(--color-ink) / <alpha-value>)",
        jade: "rgb(var(--color-brand-500) / <alpha-value>)",
        rice: "rgb(var(--color-rice) / <alpha-value>)",
        persimmon: "rgb(var(--color-persimmon) / <alpha-value>)",
        brand: {
          50: "rgb(var(--color-brand-50) / <alpha-value>)",
          100: "rgb(var(--color-brand-100) / <alpha-value>)",
          200: "rgb(var(--color-brand-200) / <alpha-value>)",
          500: "rgb(var(--color-brand-500) / <alpha-value>)",
          700: "rgb(var(--color-brand-700) / <alpha-value>)",
          800: "rgb(var(--color-brand-800) / <alpha-value>)",
          900: "rgb(var(--color-brand-900) / <alpha-value>)"
        },
        cream: {
          50: "rgb(var(--color-cream-50) / <alpha-value>)",
          100: "rgb(var(--color-cream-100) / <alpha-value>)",
          200: "rgb(var(--color-cream-200) / <alpha-value>)",
          300: "rgb(var(--color-cream-300) / <alpha-value>)"
        }
      },
      fontFamily: {
        sans: ["var(--font-sans)", "sans-serif"],
        serif: ["var(--font-serif)", "serif"]
      }
    }
  },
  plugins: []
};

export default config;
