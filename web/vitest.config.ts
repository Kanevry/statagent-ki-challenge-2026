import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Unit- und Contract-Tests; Playwright-Tests liegen unter tests/ und laufen über `pnpm test:slop` (#62).
// passWithNoTests bleibt, bis der erste Web-Test auf main liegt (#93 Punkt 4).
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    include: [
      "app/**/*.test.{ts,tsx}",
      "lib/**/*.test.{ts,tsx}",
      "components/**/*.test.{ts,tsx}",
      "landing/**/*.test.{ts,tsx}",
    ],
    passWithNoTests: true,
  },
});
