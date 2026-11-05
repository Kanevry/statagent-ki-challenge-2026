import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Unit- und Contract-Tests; Playwright-Tests liegen unter tests/ und laufen über `pnpm test:slop` (#62).
// passWithNoTests bleibt, bis der erste Web-Test auf main liegt (#93 Punkt 4).
export default defineConfig({
  plugins: [react()],
  // Wie tsconfig "paths": "@/…" zeigt auf web/ (Antrag #135). Nur "@/", damit "@kic/ui" unberührt bleibt.
  resolve: { alias: [{ find: /^@\//, replacement: fileURLToPath(new URL("./", import.meta.url)) }] },
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
