/**
 * Anti-Schablonen-Gate (Issue #62): misst mit `measureSlop` (web/tests/lib/slop-measure.js), ob eine Seite
 * die Erkennungsmuster generischer KI-Oberflächen zeigt. Alle zwölf Schlüssel müssen 0 sein.
 * Katalog, Begründung und Behebung: docs/design.md.
 */
import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test, type Page, type TestInfo } from "@playwright/test";
import { bereiche } from "../../shared/ui/src/ucs";

const hier = path.dirname(fileURLToPath(import.meta.url));
const MESSSKRIPT = path.join(hier, "lib", "slop-measure.js");
const FIXTURE = path.join(hier, "fixtures", "slop-positive.html");
const FIXTURE_VERSTECKT = path.join(hier, "fixtures", "slop-versteckt.html");
/** Harte Prüfung (#102): in CI gesetzt (Job playwright), lokal per ABGABE=1. */
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
 * Routen, die noch nicht gebaut sind: Route -> Begründung. Eine Route hier darf 404 liefern. Liefert sie 200,
 * wird sie trotzdem gemessen (0 Treffer Pflicht) und der Test hängt den Hinweis „aus NOCH_OFFEN streichen“ an,
 * statt rot zu werden, damit die Liste keine fremde Lane sperrt. Mit ABGABE=1 muss die Liste leer sein und jede
 * Route 200 liefern.
 */
const NOCH_OFFEN: Record<string, string> = {};

const ROUTEN: string[] = ["/", ...bereiche.map((uc) => uc.route), "/praesentation", "/_bausteine"];
// 120 je Viewport: UC-Unterseiten (z. B. je Lieferung) sollen das Gate nicht über die Grenze treiben (Lead 58)
const MAX_SEITEN = 120;

/** Gültiger Modell-Status mit abweichendem „zuletzt“, damit der Hinweis im Badge mitgemessen wird. */
const MODELL_STATUS = {
  provider: "azure",
  modell: "gpt-5",
  version: "2026-08-01",
  quelle: "env",
  zuletzt: {
    provider: "mistral",
    modell: "mistral-large",
    version: null,
    fallback_stufe: 2,
    zweck: "regel_entwurf",
    zeit: "2026-11-05T09:12:00+01:00",
  },
};

type Messung = { counts: Record<string, unknown>; samples?: unknown };

async function vorbereiten(page: Page): Promise<void> {
  // Kein networkidle: im Produktions-Build halten Link-Prefetches das Netz aktiv (Pipeline 41345).
  await page.waitForLoadState("load");
  await page.locator("main").first().waitFor({ state: "visible" });
  await page.evaluate(async () => {
    await document.fonts.ready;
  });
}

async function messen(page: Page, root = "body"): Promise<Messung> {
  await page.addScriptTag({ path: MESSSKRIPT });
  return page.evaluate((wurzel) => {
    // @ts-expect-error measureSlop kommt aus dem eingespielten Skript
    return measureSlop({ root: wurzel }) as Messung;
  }, root);
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

function anhangName(route: string, zustand = ""): string {
  return `slop${route === "/" ? "-start" : route.replaceAll("/", "-")}${zustand}`;
}

/** Misst die gerade geladene Seite: alle zwölf Schlüssel vorhanden und 0. Sammelt Verstöße, ohne abzubrechen. */
async function pruefeSeite(page: Page, testInfo: TestInfo, ort: string, zustand = ""): Promise<void> {
  await vorbereiten(page);
  const messung = await messen(page);
  await anhaengen(testInfo, anhangName(ort, zustand), messung);
  expect.soft(fehlendeSchluessel(messung.counts), `Schlüssel fehlen im Messergebnis (${ort}${zustand})`).toEqual([]);
  const treffer = Object.fromEntries(SCHLUESSEL.map((k) => [k, messung.counts[k]]).filter(([, v]) => v !== 0));
  expect.soft(treffer, `Treffer auf ${ort}${zustand}`).toEqual({});
}

/** Interne Seitenlinks (gleicher Ursprung, ohne API, Dateien und Anker) als Pfade. */
async function interneLinks(page: Page): Promise<string[]> {
  const pfade = await page.$$eval('a[href^="/"]', (links) =>
    links.map((a) => {
      const url = new URL((a as HTMLAnchorElement).href);
      return url.origin === location.origin ? url.pathname : "";
    }),
  );
  return [...new Set(pfade)]
    .filter((p) => p !== "")
    .map((p) => (p.length > 1 ? p.replace(/\/+$/, "") : p))
    .filter((p) => !p.startsWith("/api/") && !p.startsWith("/_next/") && !/\.[a-z0-9]{2,5}$/i.test(p));
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

  test("Negativ-Fixture: verstecktes Muster zählt in keinem Schlüssel", async ({ page }, testInfo) => {
    await page.goto(`file://${FIXTURE_VERSTECKT}`);
    const messung = await messen(page);
    await anhaengen(testInfo, "slop-versteckt", messung);
    const treffer = Object.fromEntries(SCHLUESSEL.map((k) => [k, messung.counts[k]]).filter(([, v]) => v !== 0));
    expect(treffer, "verstecktes Muster gezählt").toEqual({});
  });

  test("root body erfasst ein Muster im Header vor main, root main nicht", async ({ page }) => {
    await page.goto(`file://${FIXTURE}`);
    const ausMain = await messen(page, "main");
    const ausBody = await messen(page, "body");
    expect(ausMain.counts.kickersMono).toBe(1);
    expect(ausBody.counts.kickersMono).toBe(2);
  });

  test.describe("ohne reduzierte Bewegung", () => {
    test.use({ reducedMotion: "no-preference" });

    test("Positiv-Fixture trifft pulsingDecor", async ({ page }) => {
      await page.goto(`file://${FIXTURE}`);
      const messung = await messen(page);
      expect(messung.counts.pulsingDecor).toBeGreaterThanOrEqual(1);
    });
  });
});

test.describe("NOCH_OFFEN", () => {
  test("ist mit ABGABE=1 leer", () => {
    test.skip(!ABGABE, "Pflicht erst mit ABGABE=1");
    expect(Object.keys(NOCH_OFFEN), "Routen ungemessen").toEqual([]);
  });
});

test.describe("Anti-Schablonen-Gate", () => {
  test("Breitensuche über alle Routen und Unterseiten: 0 Treffer in zwölf Schlüsseln", async ({ page }, testInfo) => {
    test.setTimeout(900_000);
    const besucht = new Set<string>();
    const gemessen: string[] = [];
    const uebersprungen: string[] = [];
    const warteschlange: string[] = [...ROUTEN];

    while (warteschlange.length > 0 && gemessen.length < MAX_SEITEN) {
      const route = warteschlange.shift() as string;
      if (besucht.has(route)) continue;
      besucht.add(route);

      const antwort = await page.goto(route);
      const status = antwort?.status();
      const offen = route in NOCH_OFFEN && !ABGABE;
      if (offen && status === 404) {
        uebersprungen.push(`${route} (404, NOCH_OFFEN)`);
        continue;
      }
      expect.soft(status, `HTTP-Status von ${route}`).toBe(200);
      if (status !== 200) continue;
      const art = antwort?.headers()["content-type"] ?? "";
      if (!art.includes("text/html")) {
        // Eine Startroute muss eine Seite sein; ein gefundener Link auf eine Datei wird nur übergangen.
        if (ROUTEN.includes(route)) expect.soft(art, `Content-Type der Startroute ${route}`).toContain("text/html");
        continue;
      }
      if (offen) {
        testInfo.annotations.push({ type: "Hinweis", description: `${route} ist gebaut: aus NOCH_OFFEN streichen` });
      }

      await pruefeSeite(page, testInfo, route);
      gemessen.push(route);
      for (const link of await interneLinks(page)) {
        if (!besucht.has(link)) warteschlange.push(link);
      }
    }

    const ungeprueftWegenGrenze = [...new Set(warteschlange.filter((r) => !besucht.has(r)))];
    await testInfo.attach("seiten", {
      body: JSON.stringify({ gemessen, uebersprungen, ungeprueftWegenGrenze }, null, 2),
      contentType: "application/json",
    });
    expect.soft(ungeprueftWegenGrenze, `Seiten jenseits der Grenze von ${MAX_SEITEN} ungeprüft`).toEqual([]);
    expect(gemessen.length, "Keine Seite gemessen").toBeGreaterThan(0);
  });

  test("/uc3 mit Modell-Hinweis „zuletzt“ und geöffneter Protokoll-Schublade", async ({ page }, testInfo) => {
    await page.route("**/api/plattform/modell", (route) => route.fulfill({ json: MODELL_STATUS }));
    const antwort = await page.goto("/uc3");
    expect(antwort?.status(), "HTTP-Status von /uc3").toBe(200);
    await vorbereiten(page);
    await page.getByTestId("modell-zuletzt").first().waitFor({ state: "attached" });
    await pruefeSeite(page, testInfo, "/uc3", "-badge-zuletzt");

    await page.getByRole("button", { name: "Protokoll", exact: true }).click();
    const schublade = page.getByRole("dialog");
    await schublade.waitFor({ state: "visible" });
    await expect(schublade.getByText("Protokoll wird geladen.")).toHaveCount(0);
    await pruefeSeite(page, testInfo, "/uc3", "-protokoll-offen");
  });
});
