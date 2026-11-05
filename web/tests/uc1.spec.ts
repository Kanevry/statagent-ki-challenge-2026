/**
 * /uc1 SV KI-Lotse (#35) im Browser, je Projekt der Konfiguration (desktop 1440×900, mobil 390×844).
 * Das Replay läuft ohne Netz: jeder Aufruf unter /api/ wird abgebrochen. Läuft in der CI, lokal nicht auf dem M4.
 */
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const hier = path.dirname(fileURLToPath(import.meta.url));
const MESSSKRIPT = path.join(hier, "lib", "slop-measure.js");
const PFLEGE = JSON.parse(readFileSync(path.join(hier, "../components/uc1/fixtures/pflege.json"), "utf8")) as {
  schritte: Array<{ eingabe: { text: string }; antwort: { aussagen: Array<{ zitat: string }> } }>;
};
const ZITATE = PFLEGE.schritte.flatMap((s) => s.antwort.aussagen.map((a) => a.zitat));

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

async function gateMessen(page: Page, wo: string): Promise<void> {
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
  expect(treffer, `Treffer auf ${wo}`).toEqual({});
}

async function axePruefen(page: Page): Promise<void> {
  const { violations } = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  const schwer = violations.filter((v) => v.impact === "critical" || v.impact === "serious");
  expect(schwer.map((v) => `${v.id}: ${v.nodes.length}`)).toEqual([]);
}

async function bild(page: Page, name: string): Promise<void> {
  await page.screenshot({ path: test.info().outputPath(`${name}.png`), fullPage: true });
}

test("/uc1 liefert 200 mit Leer-Zustand: leeres Feld, Beispiele, keine Antwort", async ({ page }) => {
  const antwort = await page.goto("/uc1");
  expect(antwort?.status()).toBe(200);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Erzählen Sie, was los ist");
  const feld = page.getByLabel("Ihre Situation");
  await expect(feld).toHaveValue("");
  await expect(feld).toHaveAttribute("placeholder", /Ein Satz reicht/);
  await expect(page.getByRole("button", { name: "Mein Kind braucht eine Zahnspange." })).toBeVisible();
  await expect(page.locator("[data-uc1-antwort]")).toHaveCount(0);
  await bild(page, "uc1-leer");
  await axePruefen(page);
  await gateMessen(page, "/uc1 leer");
});

test("/uc1?beispiel=pflege spielt ohne Netz bis zu den Leistungen, Beleg zeigt das Zitat", async ({ page }) => {
  await page.route("**/api/**", (route) => route.abort());
  await page.goto("/uc1?beispiel=pflege");

  await expect(page.getByTestId("uc1-aufnahme")).toContainText("Aufgezeichnetes Beispiel vom");
  await expect(page.getByTestId("uc1-aufnahme")).toContainText("keine Live-Antwort");
  await expect(page.getByLabel("Ihre Situation")).toHaveValue(PFLEGE.schritte[0]?.eingabe.text ?? "");

  await expect(page.locator('[data-uc1-antwort="rueckfrage"]')).toHaveCount(1);
  await bild(page, "uc1-schritt-1-rueckfrage");

  await expect(page.locator('[data-uc1-antwort="antwort"]')).toHaveCount(1, { timeout: 15_000 });
  await expect(page.locator('[data-uc1-leistung="pflegegeld"]')).toBeVisible();
  await expect(page.getByRole("heading", { name: "Pflegegeld" })).toBeVisible();
  await bild(page, "uc1-schritt-2-leistungen");

  // KI-Kennzeichnung an jeder Antwort, mit Modellname
  const ki = page.getByTestId("uc1-ki");
  await expect(ki).toHaveCount(PFLEGE.schritte.length);
  await expect(ki.last()).toContainText("Antwort von einer KI");

  await page.getByRole("button", { name: /Beleg anzeigen/ }).first().click();
  const zitat = page.locator("[data-uc1-zitat]").first();
  await expect(zitat).toBeVisible();
  const text = (await zitat.textContent()) ?? "";
  expect(ZITATE).toContain(text.replace(/^„|“$/g, ""));
  await bild(page, "uc1-schritt-3-beleg");

  await axePruefen(page);
  await gateMessen(page, "/uc1?beispiel=pflege");
});

test("Lotse nicht erreichbar: Hinweis und „Beispiel ansehen“ spielt die Aufnahme", async ({ page }) => {
  await page.route("**/api/uc1/frage", (route) =>
    route.fulfill({ status: 503, json: { fehler: "Der Lotse ist gerade nicht erreichbar.", replay: true } }),
  );
  await page.goto("/uc1");
  await page.getByLabel("Ihre Situation").fill("Ich war drei Wochen im Spital und soll zur Reha.");
  await page.getByRole("button", { name: "Senden" }).click();
  await expect(page.getByTestId("uc1-fehler")).toContainText("Der Lotse ist gerade nicht erreichbar.");
  await page.getByRole("button", { name: "Beispiel ansehen" }).click();
  await expect(page.locator('[data-uc1-antwort="antwort"]')).toHaveCount(1, { timeout: 15_000 });
});

test("Unterseiten liefern 200 mit ehrlichem Leerzustand", async ({ page }) => {
  for (const pfad of ["/uc1/leistungen", "/uc1/antrag", "/uc1/stelle", "/uc1/anliegen"]) {
    const antwort = await page.goto(pfad);
    expect(antwort?.status(), pfad).toBe(200);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await gateMessen(page, pfad);
  }
});
