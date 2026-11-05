/**
 * /uc4 Gemeinsamer Einstieg (#98) im Browser, je Projekt der Konfiguration (desktop 1440×900, mobil 390×844).
 * Die Route POST /api/uc4/frage wird per `page.route` erfüllt: der Test prüft die Seite, nicht den Router
 * (den deckt web/lib/plattform/uc4.test.ts ab). Läuft in der CI, lokal nicht auf dem M4.
 */
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test, type Page } from "@playwright/test";

const hier = path.dirname(fileURLToPath(import.meta.url));
const uc3 = JSON.parse(readFileSync(path.join(hier, "../../shared/schema/fixtures/uc-antwort.json"), "utf8"));
const MESSSKRIPT = path.join(hier, "lib", "slop-measure.js");

/** Die zwölf Schlüssel des Anti-Schablonen-Gates, wie in slop.spec.ts (Katalog: docs/design.md). */
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

/** Misst die Seite wie slop.spec.ts (root body, nach den Schriften): alle zwölf Schlüssel vorhanden und 0. */
async function gateMessen(page: Page): Promise<void> {
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
  expect(treffer, "Treffer auf /uc4 mit Antwort").toEqual({});
}

/** Ergebnis aus drei Antworten in Kettenreihenfolge; uc2 übernimmt Zahl und Beleg von uc3 wie der Mock-Router. */
const ERGEBNIS = {
  antworten: [
    uc3,
    { ...uc3, uc: "uc2", modell: "mock", text: "Das Panel stützt sich auf die Zahl aus StatAgent." },
    { text: "Einfach erklärt: so viele Menschen hatten Arbeit.", belege: [], zahlen: [], uc: "uc1", modell: "mock", protokoll_id: null },
  ],
  fehlend: [],
};

async function frageStellen(page: Page): Promise<void> {
  await page.getByLabel("Frage an die Kette").fill("Wie viele Beschäftigte gab es 2025-03?");
  await page.getByLabel("Frage an die Kette").press("Enter");
}

test("/uc4 liefert 200 und zeigt Hauptaussage, Frage-Feld und drei leere Karten", async ({ page }) => {
  const antwort = await page.goto("/uc4");
  expect(antwort?.status()).toBe(200);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Eine Frage läuft nacheinander durch");
  await expect(page.getByLabel("Frage an die Kette")).toBeVisible();
  await expect(page.locator("[data-uc-karte]")).toHaveCount(3);
  await expect(page.locator('[data-zustand="leer"]')).toHaveCount(3);
});

test("Frage absenden: drei Karten in Reihenfolge uc3, uc2, uc1, jede Zahl mit HerkunftChip, Gate 0", async ({ page }) => {
  let gesendet: unknown = null;
  await page.route("**/api/uc4/frage", async (route) => {
    gesendet = route.request().postDataJSON();
    await route.fulfill({ json: ERGEBNIS });
  });
  await page.goto("/uc4");
  await frageStellen(page);

  const karten = page.locator("[data-uc-karte]");
  await expect(page.locator('[data-zustand="antwort"]')).toHaveCount(3);
  expect(await karten.evaluateAll((el) => el.map((k) => k.getAttribute("data-uc-karte")))).toEqual(["uc3", "uc2", "uc1"]);
  expect(gesendet).toEqual({ frage: "Wie viele Beschäftigte gab es 2025-03?" });

  const zahlen = page.locator("[data-zahl]");
  expect(await zahlen.count()).toBeGreaterThan(0);
  for (const zahl of await zahlen.all()) {
    await expect(zahl.locator('[data-baustein="herkunft"]')).toHaveCount(1);
  }
  await expect(page.getByRole("status").filter({ hasText: "3 Antworten da." })).toHaveCount(1);
  await expect(page.locator('[data-uc-karte="uc2"]').getByText("von StatAgent", { exact: true })).toHaveCount(1);

  await gateMessen(page);
});

test("gesperrter POST (Online-Demo) zeigt den Hinweis in jeder Karte, die Seite bleibt bedienbar", async ({ page }) => {
  await page.route("**/api/uc4/frage", (route) => route.fulfill({ status: 405, body: "" }));
  await page.goto("/uc4");
  await frageStellen(page);

  await expect(page.locator('[data-zustand="fehler"]')).toHaveCount(3);
  await expect(page.locator("[data-uc-karte]").getByText("Fragen sind in der Online-Demo noch gesperrt.")).toHaveCount(3);
  await expect(page.getByRole("button", { name: "Frage stellen" })).toBeEnabled();
});
