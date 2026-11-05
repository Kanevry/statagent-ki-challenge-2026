/**
 * /uc4 Gemeinsamer Einstieg (#98) im Browser, je Projekt der Konfiguration (desktop 1440×900, mobil 390×844).
 * Die Route POST /api/uc4/frage wird per `page.route` erfüllt: der Test prüft die Seite, nicht den Router
 * (den deckt web/lib/plattform/uc4.test.ts ab). Läuft in der CI, lokal nicht auf dem Entwicklungsrechner.
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

/** Der Strom zu ERGEBNIS als NDJSON, wie ihn die Route mit `Accept: application/x-ndjson` liefert. */
function strom(): string {
  const zeilen: unknown[] = [{ art: "start", kette: ["uc3", "uc2", "uc1"], modell: null }];
  ERGEBNIS.antworten.forEach((antwort, i) => {
    const uc = antwort.uc as string;
    zeilen.push({ art: "station", uc, stufe: i + 1, zustand: "laeuft" });
    zeilen.push({ art: "antwort", uc, stufe: i + 1, dauer_ms: 900, kern: String(antwort.text).split(". ")[0], antwort });
  });
  zeilen.push({ art: "ende", fehlend: [], dauer_ms: 2700 });
  return zeilen.map((z) => JSON.stringify(z)).join("\n") + "\n";
}

async function frageStellen(page: Page): Promise<void> {
  await page.getByLabel("Ihre Frage").fill("Wie viele Beschäftigte gab es 2025-03?");
  await page.getByLabel("Ihre Frage").press("Enter");
}

test("/uc4 liefert 200: Hauptaussage, Frage-Feld, drei Stationen ohne Platzhaltertext", async ({ page }) => {
  const antwort = await page.goto("/uc4");
  expect(antwort?.status()).toBe(200);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByLabel("Ihre Frage")).toBeVisible();
  await expect(page.locator("[data-uc-karte]")).toHaveCount(3);
  await expect(page.locator('[data-zustand="wartet"]')).toHaveCount(3);
  await expect(page.locator("main")).not.toContainText("sobald eine Frage gestellt ist");
});

test("Frage absenden: Stationen antworten in Reihenfolge uc3, uc2, uc1, jede mit Kernsatz, Gate 0", async ({ page }) => {
  let gesendet: unknown = null;
  let accept = "";
  await page.route("**/api/uc4/frage", async (route) => {
    gesendet = route.request().postDataJSON();
    accept = route.request().headers()["accept"] ?? "";
    await route.fulfill({ status: 200, headers: { "content-type": "application/x-ndjson" }, body: strom() });
  });
  await page.goto("/uc4");
  await frageStellen(page);

  await expect(page.locator('[data-zustand="antwort"]')).toHaveCount(3);
  const karten = page.locator("[data-uc-karte]");
  expect(await karten.evaluateAll((el) => el.map((k) => k.getAttribute("data-uc-karte")))).toEqual(["uc3", "uc2", "uc1"]);
  expect(gesendet).toEqual({ frage: "Wie viele Beschäftigte gab es 2025-03?" });
  expect(accept).toContain("application/x-ndjson");
  await expect(page.locator("[data-uc4-antwort]")).toHaveCount(3);
  await expect(page.locator('[data-uc-karte="uc3"] [data-baustein="herkunft"]')).toHaveCount(1);
  await expect(page.getByText(/Fertig in/)).toBeVisible();

  await gateMessen(page);
});

test("gesperrter POST zeigt genau einen ruhigen Satz, keine rote Meldung je Station", async ({ page }) => {
  await page.route("**/api/uc4/frage", (route) => route.fulfill({ status: 405, body: "" }));
  await page.goto("/uc4");
  await frageStellen(page);

  await expect(page.getByText("Fragen sind hier gerade nicht offen.")).toHaveCount(1);
  await expect(page.locator('[data-zustand="fehlt"]')).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Fragen", exact: true })).toBeEnabled();
});
