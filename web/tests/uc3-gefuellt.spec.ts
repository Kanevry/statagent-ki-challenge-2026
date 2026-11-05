/**
 * Vorbedingung für axe und das Anti-Schablonen-Gate auf /uc3 (#152): Die Seite zeigt die geseedeten Monatsläufe.
 * Ein Lesefehler der Datenbank liefert ebenfalls 200, dann maßen die anderen Tests nur den leeren Zustand.
 * Läuft nur mit UC3_SEED_CI=1 (CI-Job playwright nach scripts/ci/uc3_seed.py), lokal übersprungen.
 */
import { expect, test } from "@playwright/test";

const GESEEDET = ["August 2024", "September 2024", "Oktober 2024", "November 2024"];

test("/uc3 zeigt die vier geseedeten Monatsläufe, nicht den leeren Zustand", async ({ page }) => {
  test.skip(process.env.UC3_SEED_CI !== "1", "nur im CI-Job playwright mit geseedeter UC3-Datenbank");
  const antwort = await page.goto("/uc3");
  expect(antwort?.status()).toBe(200);
  const main = page.locator("main").first();
  await expect(main).not.toContainText("Noch kein Monat ist gerechnet.");
  for (const monat of GESEEDET) await expect(main).toContainText(monat);
});
