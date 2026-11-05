/**
 * UC2-Oberfläche gegen den aufgezeichneten Fall (#47), Netz gesperrt: nichts außer dem eigenen Server wird erreicht,
 * kein Sprachmodell läuft. Die Route-Handler antworten ohne Python-API mit der Aufzeichnung (Kennung mock-…).
 * Prüft Start, Strom bis "fertig", den Abbruch-Fall (U2-1a) und die Anti-Schablonen-Messung auf den UC2-Zuständen.
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

async function ohneStriche(page: Page): Promise<void> {
  const text = await page.evaluate(() => document.body.innerText);
  expect(text).not.toMatch(/[—–]/);
}

test("Fall stellen, Start, Strom bis fertig: Personas, Stand und Moderator-Spur", async ({ page }) => {
  await page.goto("/uc2");
  await expect(page.getByRole("heading", { level: 1, name: "Frage an das Panel" })).toBeVisible();
  await expect(page.getByRole("checkbox")).toHaveCount(14);
  await slopNull(page);
  await ohneStriche(page);

  await page.getByTestId("uc2-start").click();
  await expect(page).toHaveURL(/\/uc2\/panel\?fall=mock-wartezeiten$/);
  await expect(page.locator("[data-akteur]").first()).toBeVisible();
  await expect(page.locator('[data-status="laeuft"]')).toBeVisible();
  await expect(page.getByTestId("uc2-sprecher")).toContainText("Gerade spricht");

  await expect(page.locator('[data-status="fertig"]')).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId("uc2-titel")).toHaveText("Das Panel ist nach 4 Runden fertig");
  await expect(page.locator("[data-akteur]")).toHaveCount(6);
  await expect(page.locator('[data-spur="stand"][data-fertig="ja"]')).toContainText("Am Ende gilt");
  await expect(page.locator('[data-spur="moderator"]')).toContainText("denkt mit");
  await expect(page.locator('[data-akteur="aerztekammer"] [data-baustein="herkunft"]').first()).toContainText(/\d{2}\/\d{4}/);

  await page.locator('[data-akteur="aerztekammer"] [data-baustein="herkunft"] button').first().click();
  const zitat = await page.locator('[data-teil="zitat"]').first().innerText();
  expect(zitat.replace(/[„“]/g, "").length).toBeLessThanOrEqual(300);
  await slopNull(page);
  await ohneStriche(page);
});

test("Modellfehler: Runden bleiben, Erneut startet einen neuen Lauf", async ({ page }) => {
  await page.goto("/uc2/panel?fall=mock-abbruch");
  await expect(page.locator('[data-status="abgebrochen"]')).toBeVisible({ timeout: 60_000 });
  const band = page.getByRole("alert").filter({ hasText: "Runde 3 ist abgebrochen" });
  await expect(band).toContainText("Das Modell azure hat nicht rechtzeitig geantwortet.");
  await expect(band).toContainText("Die Runden 1 und 2 sind fertig und bleiben stehen.");
  await expect(band.locator('[data-teil="grund"]')).toHaveText("Technischer Grund: TimeoutError");
  await expect(page.locator("[data-akteur]")).toHaveCount(6);
  await expect(page.getByTestId("uc2-modell-ollama")).toBeDisabled();
  await expect(band).toContainText("nicht eingerichtet");
  await slopNull(page);
  await ohneStriche(page);

  await page.getByTestId("uc2-erneut").click();
  await expect(page).toHaveURL(/fall=mock-wartezeiten$/);
});

test("ohne Fall zeigt Panel den Leerzustand mit Weg zum Fall", async ({ page }) => {
  await page.goto("/uc2/panel");
  await expect(page.getByRole("link", { name: "Fall stellen", exact: true }).last()).toBeVisible();
  await expect(page.getByText("Es läuft noch keine Verhandlung.")).toBeVisible();
  await slopNull(page);
});
