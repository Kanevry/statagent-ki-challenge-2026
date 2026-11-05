/**
 * /praesentation Folienschau (#59, Lane E5) im Browser, je Projekt der Konfiguration (desktop 1440×900, mobil 390×844).
 * Die Folien kommen aus web/content/slides/; der Test liest dieselben Dateien und findet Szenen über `szene:` im
 * Frontmatter bzw. `data-szene` im DOM, nie über feste Foliennummern. Läuft in der CI, nicht lokal.
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

const dateien = readdirSync(ORDNER)
  .filter((n) => n.endsWith(".md") && !/^readme\.md$/i.test(n))
  .sort((a, b) => a.localeCompare(b, "de", { numeric: true }))
  .map((n) => readFileSync(path.join(ORDNER, n), "utf8").replace(/\r\n?/g, "\n"));
const ANZAHL = dateien.length;
const NOTIZ = /^\s*(?:<!--\s*notizen\s*-->|##\s+Sprechernotizen)\s*$/im;

/** Nummer (ab 1) der Folie mit `szene: <id>`, oder 0. */
function folieMitSzene(id: string): number {
  return dateien.findIndex((q) => new RegExp(`^szene:\\s*${id}\\s*$`, "m").test(q)) + 1;
}

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

// Der Modell-Badge im Kopf fragt /api/plattform/modell. In CI läuft kein Modell-Schalter, die Route antwortet 503
// und der Browser meldet das als Ladefehler. Das ist kein Fehler der Präsentation und wird hier nicht gezählt.
const BEKANNTE_LADEFEHLER = ["/api/plattform/modell"];

/** Sammelt Konsolenfehler und unbehandelte Fehler der Seite. */
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

async function bereit(page: Page, folie?: number | string): Promise<void> {
  await page.goto(folie === undefined ? "/praesentation" : `/praesentation?folie=${folie}`);
  await page.locator("[data-folie]").waitFor({ state: "visible" });
  // Tasten gehen an das Fenster; der Fokus liegt auf dem Dokument, nicht in einem Feld.
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
}

const aktuelleFolie = (page: Page) => page.locator("[data-folie]").getAttribute("data-folie");
const aktiveSzene = (page: Page) => page.locator('[data-aktiv="ja"]');

test.describe("mit reduzierter Bewegung", () => {
  test.use({ reducedMotion: "reduce" });

  test("Seite lädt ohne Konsolenfehler, Pfeil rechts wechselt bis zum Ende, Neuladen bleibt auf der Folie", async ({ page }) => {
    const fehler = fehlerSammeln(page);
    await bereit(page);
    expect(await aktuelleFolie(page)).toBe("1");
    // Bei reduzierter Bewegung zeigt jede Szene sofort alle Takte, ein Druck heißt also immer nächste Folie.
    for (let i = 2; i <= ANZAHL; i++) {
      await page.keyboard.press("ArrowRight");
      await expect(page).toHaveURL(new RegExp(`[?&]folie=${i}(&|$)`));
      await expect(aktiveSzene(page)).toBeVisible();
    }
    await page.reload();
    await page.locator("[data-folie]").waitFor({ state: "visible" });
    expect(await aktuelleFolie(page)).toBe(String(ANZAHL));
    await page.keyboard.press("ArrowLeft");
    await expect(page).toHaveURL(new RegExp(`[?&]folie=${ANZAHL - 1}(&|$)`));
    expect(fehler, "Konsolenfehler beim Durchblättern").toEqual([]);
  });

  test("?folie=N öffnet Folie N, ungültige Werte öffnen Folie 1", async ({ page }) => {
    await bereit(page, ANZAHL);
    expect(await aktuelleFolie(page)).toBe(String(ANZAHL));
    for (const ungueltig of ["0", "999", "abc", "-3", "2x"]) {
      await bereit(page, ungueltig);
      expect(await aktuelleFolie(page)).toBe("1");
    }
  });

  test("die Szene beleg zeigt sofort die Endzahl aus dem Frontmatter", async ({ page }) => {
    const nr = folieMitSzene("beleg");
    test.skip(nr === 0, "keine Folie mit szene: beleg");
    const zahl = /^zahl:\s*(.+?)\s*$/m.exec(dateien[nr - 1] ?? "")?.[1]?.split(" von ")[0] ?? "";
    await bereit(page, nr);
    await expect(page.locator('[data-szene="beleg"]')).toBeVisible();
    await expect(page.locator('[data-szene="beleg"]')).toContainText(zahl);
  });

  test("Taste N blendet den Sprechtext ein und wieder aus, auf der Bühne steht er nie", async ({ page }) => {
    await bereit(page, 1);
    const notizen = page.getByRole("region", { name: "Sprechnotizen" });
    await expect(notizen).toHaveCount(0);
    await page.keyboard.press("n");
    await expect(notizen).toBeVisible();
    const satz = ersteNotiz(1);
    if (satz) {
      await expect(notizen).toContainText(satz.slice(0, 40));
      await expect(aktiveSzene(page)).not.toContainText(satz.slice(0, 40));
    }
    await page.keyboard.press("n");
    await expect(notizen).toHaveCount(0);
  });

  test("Taste F schaltet den Vollbildmodus", async ({ page }, info) => {
    test.skip(info.project.name === "mobil", "Vollbild ist nur am Rechner Teil der Vorführung");
    await bereit(page, 1);
    await page.keyboard.press("f");
    await expect.poll(() => page.evaluate(() => document.fullscreenElement !== null)).toBe(true);
    await expect(page.locator("[data-vollbild]")).toHaveAttribute("data-vollbild", "an");
    await page.keyboard.press("f");
    await expect.poll(() => page.evaluate(() => document.fullscreenElement !== null)).toBe(false);
    await expect(page.locator("[data-vollbild]")).toHaveAttribute("data-vollbild", "aus");
  });

  test("Anti-Schablonen-Gate: jede Folie mit offenen Sprechnotizen zeigt 0 Treffer", async ({ page }) => {
    await bereit(page, 1);
    await page.keyboard.press("n");
    await page.evaluate(async () => {
      await document.fonts.ready;
    });
    await page.addScriptTag({ path: MESSSKRIPT });
    for (let i = 1; i <= ANZAHL; i++) {
      const counts = await page.evaluate(() => {
        // @ts-expect-error measureSlop kommt aus dem eingespielten Skript
        return (measureSlop({ root: "body" }) as { counts: Record<string, unknown> }).counts;
      });
      expect(SCHLUESSEL.filter((k) => !(k in counts)), "Schlüssel fehlen im Messergebnis").toEqual([]);
      const treffer = Object.fromEntries(SCHLUESSEL.map((k) => [k, counts[k]]).filter(([, v]) => v !== 0));
      expect(treffer, `Treffer auf /praesentation, Folie ${i}`).toEqual({});
      if (i < ANZAHL) await page.keyboard.press("ArrowRight");
    }
  });
});

test.describe("mit Bewegung", () => {
  test.use({ reducedMotion: "no-preference" });

  test("die Szene falsche-zahl braucht drei Pfeil rechts für die Takte, dann kommt die nächste Folie", async ({ page }) => {
    const nr = folieMitSzene("falsche-zahl");
    test.skip(nr === 0 || nr === ANZAHL, "keine Folie mit szene: falsche-zahl vor dem Ende");
    const fehler = fehlerSammeln(page);
    const buehne = page.locator("[data-folie]");
    // Der Direktlink öffnet die Szene im Endzustand mit allen Takten (UI-Regie, keine Zwischenstände).
    await bereit(page, nr);
    await expect(buehne).toHaveAttribute("data-takt", "3");
    // Von der vorigen Folie mit Pfeil rechts betreten: Takt 0, dann schalten drei Pfeile die Takte.
    await bereit(page, nr - 1);
    await page.keyboard.press("ArrowRight");
    await expect(page.locator('[data-szene="falsche-zahl"]')).toBeVisible();
    await expect(buehne).toHaveAttribute("data-folie", String(nr));
    await expect(buehne).toHaveAttribute("data-takt", "0");
    for (const takt of ["1", "2", "3"]) {
      await page.keyboard.press("ArrowRight");
      await expect(buehne).toHaveAttribute("data-takt", takt);
      await expect(buehne).toHaveAttribute("data-folie", String(nr));
    }
    await page.keyboard.press("ArrowRight");
    await expect(buehne).toHaveAttribute("data-folie", String(nr + 1));
    await expect(page).toHaveURL(new RegExp(`[?&]folie=${nr + 1}(&|$)`));
    // Zurück betritt die Szene von hinten: alle Takte gezeigt.
    await page.keyboard.press("ArrowLeft");
    await expect(buehne).toHaveAttribute("data-folie", String(nr));
    await expect(buehne).toHaveAttribute("data-takt", "3");
    expect(fehler).toEqual([]);
  });
});
