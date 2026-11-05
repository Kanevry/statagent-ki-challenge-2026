/**
 * Anti-Schablonen-Gate (Issue #62): misst mit `measureSlop` (web/tests/lib/slop-measure.js), ob eine Seite
 * die Erkennungsmuster generischer KI-Oberflächen zeigt. Alle zwölf Schlüssel müssen 0 sein.
 * Katalog, Begründung und Behebung: docs/design.md.
 */
import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test, type Page, type TestInfo } from "@playwright/test";
import { ucs } from "../../shared/ui/src/ucs";

const hier = path.dirname(fileURLToPath(import.meta.url));
const MESSSKRIPT = path.join(hier, "lib", "slop-measure.js");
const FIXTURE = path.join(hier, "fixtures", "slop-positive.html");
const ABGABE = process.env.ABGABE === "1";

/** Die zwölf geprüften Schlüssel. `genericFontShare` ist ausgenommen (Inter ist Vertrag, siehe docs/design.md). */
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

/**
 * Routen, die noch nicht gebaut sind: Route -> Begründung. Das ist der EINZIGE Weg, eine Route
 * auszunehmen. Eine Route hier MUSS 404 liefern; sobald sie gebaut ist, wird der Test rot und verlangt,
 * den Eintrag zu streichen. Mit ABGABE=1 muss die Liste leer sein.
 */
const NOCH_OFFEN: Record<string, string> = {
  "/": "Landing-Session baut die Startseite noch",
};

const ROUTEN: string[] = ["/", ...ucs.map((uc) => uc.route), "/praesentation", "/_bausteine"];

type Messung = { counts: Record<string, unknown>; samples?: unknown };

async function vorbereiten(page: Page): Promise<void> {
  // Kein networkidle: im Produktions-Build halten Link-Prefetches das Netz aktiv (Pipeline 41345).
  await page.waitForLoadState("load");
  await page.locator("main").first().waitFor({ state: "visible" });
  await page.evaluate(async () => {
    await document.fonts.ready;
  });
}

async function messen(page: Page): Promise<Messung> {
  await page.addScriptTag({ path: MESSSKRIPT });
  return page.evaluate(() => {
    // @ts-expect-error measureSlop kommt aus dem eingespielten Skript
    return measureSlop({ root: "body" }) as Messung;
  });
}

async function anhaengen(testInfo: TestInfo, name: string, messung: Messung): Promise<void> {
  const werte = Object.fromEntries(SCHLUESSEL.map((k) => [k, messung.counts[k]]));
  await testInfo.attach(name, {
    body: JSON.stringify({ werte, samples: messung.samples ?? null }, null, 2),
    contentType: "application/json",
  });
}

function fehlendeSchluessel(counts: Record<string, unknown>): string[] {
  return SCHLUESSEL.filter((k) => !Object.keys(counts).includes(k));
}

function anhangName(route: string): string {
  return `slop${route === "/" ? "-start" : route.replaceAll("/", "-")}`;
}

/** Misst eine Route: HTTP 200, alle zwölf Schlüssel vorhanden und 0. */
async function pruefeRoute(page: Page, testInfo: TestInfo, route: string): Promise<void> {
  const antwort = await page.goto(route);
  expect(antwort?.status(), `HTTP-Status von ${route}`).toBe(200);
  await vorbereiten(page);
  const messung = await messen(page);
  await anhaengen(testInfo, anhangName(route), messung);
  expect(fehlendeSchluessel(messung.counts), "Schlüssel fehlen im Messergebnis").toEqual([]);
  const treffer = Object.fromEntries(SCHLUESSEL.map((k) => [k, messung.counts[k]]).filter(([, v]) => v !== 0));
  expect(treffer, `Treffer auf ${route}`).toEqual({});
}

test.use({ reducedMotion: "reduce" });

test.describe("Messfunktion", () => {
  test("Positiv-Fixture liefert in allen zwölf Schlüsseln mindestens 1", async ({ page }, testInfo) => {
    await page.goto(`file://${FIXTURE}`);
    const messung = await messen(page);
    await anhaengen(testInfo, "slop-positive", messung);

    expect(fehlendeSchluessel(messung.counts), "Schlüssel fehlen im Messergebnis").toEqual([]);
    for (const k of SCHLUESSEL) {
      expect(messung.counts[k], `Positiv-Fixture trifft ${k} nicht`).toBeGreaterThanOrEqual(1);
    }
  });
});

test.describe("NOCH_OFFEN", () => {
  test("ist vor der Abgabe leer", () => {
    test.skip(!ABGABE, "Pflicht erst mit ABGABE=1");
    expect(Object.keys(NOCH_OFFEN), "Routen ungemessen").toEqual([]);
  });

  for (const route of Object.keys(NOCH_OFFEN)) {
    test(`${route} ist noch nicht gebaut`, async ({ page }) => {
      const antwort = await page.goto(route);
      expect(antwort?.status(), `Route ${route} gebaut, aus NOCH_OFFEN streichen`).toBe(404);
    });
  }
});

test.describe("Anti-Schablonen-Gate", () => {
  for (const route of ROUTEN.filter((r) => !(r in NOCH_OFFEN))) {
    test(`${route}: 0 Treffer in zwölf Schlüsseln, auch auf Unterseiten`, async ({ page }, testInfo) => {
      await pruefeRoute(page, testInfo, route);

      // Unterseiten eines UC (z. B. /uc3/lauf) über die Links der Seite mitnehmen.
      if (route.startsWith("/uc")) {
        const unterseiten = await page.$$eval(
          `a[href^="${route}/"]`,
          (links) => [...new Set(links.map((a) => new URL((a as HTMLAnchorElement).href).pathname))],
        );
        for (const unterseite of unterseiten) await pruefeRoute(page, testInfo, unterseite);
      }
    });
  }
});
