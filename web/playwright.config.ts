import { defineConfig, devices } from "@playwright/test";

// Anti-Schablonen-Gate (#62). Der Dev-Server läuft auf festem Port, damit der Test ohne weitere Einrichtung startet.
const PORT = 3210;
const IN_CI = Boolean(process.env.CI);

export default defineConfig({
  testDir: "tests",
  testMatch: "**/*.spec.ts",
  fullyParallel: true,
  forbidOnly: IN_CI,
  retries: 0,
  // Erste Kompilierung der Routen im Dev-Server dauert; Seitenaufrufe bekommen Luft.
  timeout: 90_000,
  reporter: [
    ["list"],
    ["json", { outputFile: "test-results/slop-report.json" }],
    ["html", { outputFolder: "playwright-report", open: "never" }],
  ],
  use: {
    baseURL: `http://localhost:${PORT}`,
    navigationTimeout: 90_000,
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
    {
      name: "mobil",
      // Nur Chromium: Gerätevorlage ohne Browserwechsel, Viewport 390x844.
      use: { ...devices["Desktop Chrome"], viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true },
    },
  ],
  webServer: {
    // CI misst den Produktions-Build (so, wie die Jury die App sieht); lokal reicht der Dev-Server.
    command: IN_CI ? `pnpm exec next build && pnpm exec next start -p ${PORT}` : `pnpm exec next dev -p ${PORT}`,
    cwd: ".",
    // `port` statt `url`: solange `/` noch 404 liefert, gilt eine URL-Prüfung nie als bereit.
    port: PORT,
    // nie einen fremden Server auf demselben Port mitmessen (geteilte Rechner)
    reuseExistingServer: false,
    timeout: IN_CI ? 420_000 : 180_000,
    stdout: "ignore",
    stderr: "pipe",
    // KIC_FIXTURE: die Protokoll-Schublade zeigt Einträge, damit sie gefüllt gemessen wird.
    env: { LLM_PROVIDER: "mock", KIC_BAUSTEINE: "1", KIC_FIXTURE: "1" },
  },
});
