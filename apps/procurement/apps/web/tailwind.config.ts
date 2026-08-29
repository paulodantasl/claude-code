import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#f5f7fb",
          500: "#3b5bdb",
          600: "#324bc4",
          700: "#283e9d",
        },
      },
    },
  },
  plugins: [],
};

export default config;
