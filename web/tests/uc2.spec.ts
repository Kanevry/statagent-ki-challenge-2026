/**
 * UC2-Oberfläche gegen den aufgezeichneten Fall (#47), Netz gesperrt: nichts außer dem eigenen Server wird erreicht,
 * kein Sprachmodell läuft. Die Route-Handler antworten ohne Python-API mit der Aufzeichnung (Kennung mock-…).
 * Prüft die Journey Fall → Bühne → Ergebnis und die Anti-Schablonen-Messung auf den UC2-Zuständen.
 */
import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test, type Page } from "@playwright/test";

const MESSSKRIPT = path.join(path.dirname(fileURLToPath(import.meta.url)), "lib", "slop-measure.js");
const SCHLUESSEL = [
  "kickersMono",
  "kickersCaps",
  "iconTiles",
  "shadowCards",
  "ghostCards",
  "gradientText",
  "glassBlur",
  "lightOrbs",
  "pulsingDecor",
  "sparklesNonAi",
  "emDashes",
  "questionHeadings",
] as const;

test.use({ reducedMotion: "reduce" });

test.beforeEach(async ({ page, baseURL }) => {
  await page.route(
    (url) => !url.href.startsWith(String(baseURL)) && !url.protocol.startsWith("data"),
    (route) => route.abort(),
  );
});

async function slopNull(page: Page): Promise<void> {
  await page.addScriptTag({ path: MESSSKRIPT });
  const counts = await page.evaluate(() => {
    // @ts-expect-error measureSlop kommt aus dem eingespielten Skript
    return measureSlop({ root: "body" }).counts as Record<string, number>;
  });
  const treffer = Object.fromEntries(SCHLUESSEL.map((k) => [k, counts[k]]).filter(([, v]) => v !== 0));
  expect(treffer, "Schablonen-Treffer").toEqual({});
}

/** Kein horizontales Scrollen: bei 390 px Breite darf die Seite nicht breiter sein als der Bildschirm. */
async function passtInDieBreite(page: Page): Promise<void> {
  const breite = page.viewportSize()!.width;
  const scroll = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(scroll, `scrollWidth ${scroll} bei Fensterbreite ${breite}`).toBeLessThanOrEqual(breite);
}

async function ohneStriche(page: Page): Promise<void> {
  const text = await page.evaluate(() => document.body.innerText);
  expect(text).not.toMatch(/[—–]/);
}

test("Fall, Verhandlung ansehen, ein Sprecher zur Zeit, Ergebnis mit Freigabe", async ({ page }) => {
  await page.goto("/uc2");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Wartezeiten");
  // Eine Hauptaktion, keine wirkungslose Auswahl, keine Sperre.
  await expect(page.getByRole("checkbox")).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Verhandlung ansehen" })).toHaveCount(1);
  await expect(page.locator("main")).not.toContainText("gesperrt");
  await slopNull(page);
  await ohneStriche(page);
  await passtInDieBreite(page);

  await page.getByRole("link", { name: "Verhandlung ansehen" }).click();
  await expect(page).toHaveURL(/\/uc2\/panel\?fall=mock-wartezeiten$/);
  await expect(page.getByTestId("uc2-buehne")).toBeVisible();
  // Genau ein Sitz ist der aktuelle Sprecher.
  await expect(page.locator('nav[aria-label="Am Tisch"] [aria-current="true"]')).toHaveCount(1, { timeout: 30_000 });
  await expect(page.locator("main")).toContainText("Runde 1");
  await slopNull(page);
  await ohneStriche(page);
  await passtInDieBreite(page);

  // Ein Klick reicht, und das Ergebnis steht sofort da (Live-Test 05.11.: drei Klicks, 15 s).
  await page.getByRole("button", { name: "Zum Ergebnis" }).click();
  await expect(page.locator("main")).toContainText("Ergebnis nach 4 Runden", { timeout: 5_000 });
  await expect(page.getByRole("heading", { name: "Ergebnis freigeben" })).toBeVisible();
  await expect(page.locator("main")).not.toContainText("mock-fixture");
  await slopNull(page);
  await ohneStriche(page);
  await passtInDieBreite(page);
});

test("ohne Fall zeigt Panel genau eine Aktion", async ({ page }) => {
  await page.goto("/uc2/panel");
  await expect(page.getByText("Es läuft gerade keine Verhandlung.")).toBeVisible();
  await expect(page.getByRole("link", { name: "Verhandlung ansehen" })).toBeVisible();
  await slopNull(page);
  await passtInDieBreite(page);
});

test("unbekannter Fall sagt das in einem Satz", async ({ page }) => {
  await page.goto("/uc2/panel?fall=mock-gibt-es-nicht");
  await expect(page.getByText("Diese Verhandlung gibt es nicht.")).toBeVisible({ timeout: 30_000 });
  await slopNull(page);
  await passtInDieBreite(page);
});
