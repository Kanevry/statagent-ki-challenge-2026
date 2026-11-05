/**
 * /praesentation Folienschau (#59) im Browser, je Projekt der Konfiguration (desktop 1440×900, mobil 390×844).
 * Die Folien kommen aus web/content/slides/; der Test liest dieselben Dateien und hängt an keinem festen Text,
 * damit er auch hält, wenn die Beispiel-Folien durch die echten ersetzt werden. Läuft in der CI, lokal nicht auf dem M4.
 */
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test, type Page } from "@playwright/test";

const hier = path.dirname(fileURLToPath(import.meta.url));
const ORDNER = path.join(hier, "..", "content", "slides");
const MESSSKRIPT = path.join(hier, "lib", "slop-measure.js");

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

const dateien = readdirSync(ORDNER)
  .filter((n) => n.endsWith(".md") && !/^readme\.md$/i.test(n))
  .sort((a, b) => a.localeCompare(b, "de", { numeric: true }))
  .map((n) => readFileSync(path.join(ORDNER, n), "utf8").replace(/\r\n?/g, "\n"));
const ANZAHL = dateien.length;
const NOTIZ = /^\s*(?:<!--\s*notizen\s*-->|##\s+Sprechernotizen)\s*$/im;

/** Erste Textzeile des Sprechtexts einer Folie (1-basiert), oder null. */
function ersteNotiz(nr: number): string | null {
  const quelle = dateien[nr - 1] ?? "";
  const treffer = NOTIZ.exec(quelle);
  if (!treffer) return null;
  const zeile = quelle
    .slice(treffer.index + treffer[0].length)
    .split("\n")
    .map((z) => z.trim())
    .find((z) => z !== "");
  return zeile ?? null;
}

const live = dateien.findIndex((q) => /^layout:\s*live\s*$/m.test(q) && /^route:\s*\S+/m.test(q));
const LIVE_NR = live + 1;

/** Sammelt Konsolenfehler und unbehandelte Fehler der Seite. */
// Der Modell-Badge im Kopf fragt /api/plattform/modell. In CI läuft kein Modell-Schalter, die Route antwortet 503
// und der Browser meldet das als Ladefehler. Das ist kein Fehler der Präsentation und wird hier nicht gezählt.
const BEKANNTE_LADEFEHLER = ["/api/plattform/modell"];

function fehlerSammeln(page: Page): string[] {
  const fehler: string[] = [];
  page.on("console", (m) => {
    if (m.type() !== "error") return;
    const quelle = m.location().url ?? "";
    if (BEKANNTE_LADEFEHLER.some((pfad) => quelle.includes(pfad))) return;
    fehler.push(`${m.text()}${quelle ? ` (${quelle})` : ""}`);
  });
  page.on("pageerror", (e) => fehler.push(e.message));
  return fehler;
}

async function bereit(page: Page, folie?: string): Promise<void> {
  await page.goto(folie === undefined ? "/praesentation" : `/praesentation?folie=${folie}`);
  await page.locator("[data-folie]").waitFor({ state: "visible" });
  // Tasten gehen an das Fenster; der Fokus liegt auf dem Dokument, nicht in einem Feld.
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
}

const aktuelleFolie = (page: Page) => page.locator("[data-folie]").getAttribute("data-folie");

test("es gibt mindestens zwei Folien und eine live-Folie mit Route", () => {
  expect(ANZAHL).toBeGreaterThanOrEqual(2);
  expect(LIVE_NR, "keine Folie mit layout: live und route").toBeGreaterThan(0);
});

test("ohne Parameter Folie 1; Pfeil rechts führt zu ?folie=2, Neuladen bleibt dort, Pfeil links zurück", async ({ page }) => {
  await bereit(page);
  expect(await aktuelleFolie(page)).toBe("1");

  await page.keyboard.press("ArrowRight");
  await expect(page).toHaveURL(/[?&]folie=2(&|$)/);
  expect(await aktuelleFolie(page)).toBe("2");

  await page.reload();
  await page.locator("[data-folie]").waitFor({ state: "visible" });
  expect(await aktuelleFolie(page)).toBe("2");

  await page.keyboard.press("ArrowLeft");
  await expect(page).toHaveURL(/[?&]folie=1(&|$)/);
});

test("Knöpfe Nächste und Vorherige Folie wechseln und sind am Rand gesperrt", async ({ page }) => {
  await bereit(page, "1");
  await expect(page.getByRole("button", { name: "Vorherige Folie" })).toBeDisabled();
  await page.getByRole("button", { name: "Nächste Folie" }).click();
  await expect(page).toHaveURL(/[?&]folie=2(&|$)/);
  await page.getByRole("button", { name: "Vorherige Folie" }).click();
  await expect(page).toHaveURL(/[?&]folie=1(&|$)/);
  await bereit(page, String(ANZAHL));
  await expect(page.getByRole("button", { name: "Nächste Folie" })).toBeDisabled();
});

for (const ungueltig of ["0", "999", "abc", "-3", "2x"]) {
  test(`?folie=${ungueltig} öffnet Folie 1`, async ({ page }) => {
    await bereit(page, ungueltig);
    expect(await aktuelleFolie(page)).toBe("1");
  });
}

test("Taste N blendet den Sprechtext ein und wieder aus, auf der Folie steht er nie", async ({ page }) => {
  await bereit(page, "1");
  const notizen = page.getByRole("region", { name: "Sprechnotizen" });
  await expect(notizen).toHaveCount(0);

  await page.keyboard.press("n");
  await expect(notizen).toBeVisible();
  const satz = ersteNotiz(1);
  if (satz) {
    await expect(notizen).toContainText(satz.slice(0, 40));
    await expect(page.locator("[data-folie]")).not.toContainText(satz.slice(0, 40));
  }

  await page.keyboard.press("n");
  await expect(notizen).toHaveCount(0);
});

test("Taste F schaltet den Vollbildmodus", async ({ page }, info) => {
  test.skip(info.project.name === "mobil", "Vollbild ist nur am Rechner Teil der Vorführung");
  await bereit(page, "1");
  await page.keyboard.press("f");
  await expect.poll(() => page.evaluate(() => document.fullscreenElement !== null)).toBe(true);
  await expect(page.locator("[data-vollbild]")).toHaveAttribute("data-vollbild", "an");

  await page.keyboard.press("f");
  await expect.poll(() => page.evaluate(() => document.fullscreenElement !== null)).toBe(false);
  await expect(page.locator("[data-vollbild]")).toHaveAttribute("data-vollbild", "aus");
});

test("die live-Folie zeigt den UC3-Inhalt in der Folie, ohne iframe und ohne Konsolenfehler", async ({ page }) => {
  const fehler = fehlerSammeln(page);
  await bereit(page, String(LIVE_NR));
  const hinweis = page.locator("[data-live-route]");
  await expect(hinweis).toBeVisible();
  await expect(hinweis.getByRole("heading", { name: "StatAgent" })).toBeVisible();
  await expect(page.locator("iframe")).toHaveCount(0);
  expect(fehler, "Konsolenfehler auf der live-Folie").toEqual([]);
});

test("alle Folien rendern ohne Konsolenfehler", async ({ page }) => {
  const fehler = fehlerSammeln(page);
  await bereit(page, "1");
  for (let i = 2; i <= ANZAHL; i++) {
    await page.keyboard.press("ArrowRight");
    await expect(page).toHaveURL(new RegExp(`[?&]folie=${i}(&|$)`));
    await expect(page.locator("[data-folie]")).toHaveAttribute("data-folie", String(i));
  }
  expect(fehler, "Konsolenfehler beim Durchblättern").toEqual([]);
});

test("Anti-Schablonen-Gate: Folie mit offenen Sprechnotizen zeigt 0 Treffer", async ({ page }) => {
  await bereit(page, "1");
  await page.keyboard.press("n");
  await page.evaluate(async () => {
    await document.fonts.ready;
  });
  await page.addScriptTag({ path: MESSSKRIPT });
  const counts = await page.evaluate(() => {
    // @ts-expect-error measureSlop kommt aus dem eingespielten Skript
    return (measureSlop({ root: "body" }) as { counts: Record<string, unknown> }).counts;
  });
  expect(SCHLUESSEL.filter((k) => !(k in counts)), "Schlüssel fehlen im Messergebnis").toEqual([]);
  const treffer = Object.fromEntries(SCHLUESSEL.map((k) => [k, counts[k]]).filter(([, v]) => v !== 0));
  expect(treffer, "Treffer auf /praesentation").toEqual({});
});
