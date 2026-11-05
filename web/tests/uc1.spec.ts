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
  schritte: Array<{ eingabe: { text: string }; antwort: { aussagen: Array<{ zitat: string }> } & Record<string, unknown> }>;
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

test("/uc1?beispiel=pflege spielt ohne Netz bis zu Antrag und Stelle", async ({ page }) => {
  await page.route("**/api/**", (route) => route.abort());
  await page.goto("/uc1?beispiel=pflege");

  const aufnahme = page.getByTestId("uc1-aufnahme");
  await expect(aufnahme).toContainText("Aufgezeichnetes Beispiel vom");
  await expect(aufnahme).toContainText("keine Live-Antwort");
  await expect(aufnahme).toContainText("Alle Personenangaben sind erfunden.");

  // Rückfrage als Hauptaussage, die Situation nur klein darüber, das große Eingabefeld ist weg.
  await expect(page.locator('[data-uc1-antwort="rueckfrage"]')).toHaveCount(1);
  await expect(page.locator('[data-uc1-antwort="rueckfrage"]')).toContainText("Wer zahlt die Pension?");
  await expect(page.getByTestId("uc1-situation-kurz")).toContainText(PFLEGE.schritte[0]?.eingabe.text ?? "");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Eine Angabe fehlt noch");
  await expect(page.getByLabel("Ihre Situation")).toHaveCount(0);
  // Während die Aufnahme läuft, geht nichts live hinaus.
  await expect(page.getByRole("button", { name: "Antworten" })).toHaveAttribute("aria-disabled", "true");
  await bild(page, "uc1-schritt-1-rueckfrage");

  // Leistungen als Hauptaussage oben, der Fokus steht auf der neuen Überschrift.
  await expect(page.locator('[data-uc1-antwort="antwort"]')).toHaveCount(1, { timeout: 15_000 });
  const titel = page.getByRole("heading", { level: 1 });
  await expect(titel).toHaveText("Das kommt für Sie in Frage");
  await expect(titel).toBeFocused();
  await expect(page.locator('[data-uc1-leistung="pflegegeld"]')).toBeVisible();
  await expect(page.getByRole("heading", { name: "Pflegegeld" })).toBeVisible();
  // Für Reha gibt es keine Aufnahme: kein Knopf, der ins Leere führt, sondern ein ehrlicher Satz.
  const reha = page.locator('[data-uc1-leistung="rehabilitation"]');
  await expect(reha).toBeVisible();
  await expect(reha).toContainText("Im Beispiel ist er nicht aufgezeichnet.");
  await expect(reha.getByRole("button", { name: "Antrag vorbereiten" })).toHaveCount(0);
  await bild(page, "uc1-schritt-2-leistungen");

  // KI-Kennzeichnung an jeder Antwort, mit Modellname (frühere Schritte eingeklappt, aber vorhanden)
  const ki = page.getByTestId("uc1-ki");
  await expect(ki).toHaveCount(PFLEGE.schritte.length);
  await expect(ki.first()).toContainText("Antwort von einer KI");

  // Beleg-Chip in der Optik des HerkunftChip: aufklappen zeigt das Zitat wörtlich.
  const chip = page.locator('[data-baustein="herkunft"]').first().getByRole("button", { name: /Zitat ansehen/ });
  await chip.click();
  await expect(chip).toHaveAttribute("aria-expanded", "true");
  const zitat = page.locator("[data-uc1-zitat]").first();
  await expect(zitat).toBeVisible();
  const text = (await zitat.textContent()) ?? "";
  expect(ZITATE).toContain(text.trim());
  await bild(page, "uc1-schritt-2-beleg");
  await axePruefen(page);
  await gateMessen(page, "/uc1?beispiel=pflege");

  // „ändern“ bringt das Eingabefeld mit der Situation zurück.
  await page.getByRole("button", { name: "ändern" }).click();
  await expect(page.getByLabel("Ihre Situation")).toHaveValue(PFLEGE.schritte[0]?.eingabe.text ?? "");
  await page.getByRole("button", { name: "Zurück zur Antwort" }).click();

  // Schritt 3: Antrag aus der Aufnahme, ohne Netz.
  await page.getByRole("button", { name: "Antrag vorbereiten" }).click();
  await expect(page).toHaveURL(/\/uc1\/antrag$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Pflegegeld: Antrag vorbereitet");
  await expect(page.getByTestId("uc1-aufnahme")).toContainText("Beispiel");
  await expect(page.getByRole("cell", { name: "Maria" })).toBeVisible();
  await expect(page.getByText("bitte ergänzen").first()).toBeVisible();
  await expect(page.getByText("Abgeschickt wird nichts. Sie prüfen, unterschreiben und senden selbst.")).toBeVisible();
  // Im Replay gibt es kein PDF und nichts, was etwas abschickt.
  await expect(page.getByRole("link", { name: "Antrag als PDF speichern" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /abschicken|absenden|einreichen/i })).toHaveCount(0);
  await bild(page, "uc1-schritt-3-antrag");
  await axePruefen(page);
  await gateMessen(page, "/uc1/antrag (Beispiel)");

  // Freigabe des Entwurfs: erst nach Vor- und Nachnamen gilt er als geprüft. „Maria Muster“ lehnt die Namensregel
  // ab (Platzhalter „muster“), deshalb ein echter Name.
  const stand = page.getByTestId("uc1-entwurf-stand");
  await expect(stand).toHaveText("Entwurf nicht geprüft");
  await expect(page.getByText("Die Prüfung gilt für diesen Entwurf auf diesem Gerät. Abgeschickt wird nichts.")).toBeVisible();
  const name = page.getByLabel("Vor- und Nachname");
  await name.fill("Team");
  await expect(page.getByRole("button", { name: "Freigeben" })).toBeDisabled();
  await name.fill("Maria Huber");
  await page.getByRole("button", { name: "Freigeben" }).click();
  await expect(stand).toContainText("Entwurf geprüft von Maria Huber");
  await bild(page, "uc1-schritt-3-geprueft");
  await axePruefen(page);
  await gateMessen(page, "/uc1/antrag (geprüft)");

  // Schritt 4: zuständige Stelle mit Beleg.
  await page.getByRole("link", { name: "Weiter zur zuständigen Stelle" }).click();
  await expect(page).toHaveURL(/\/uc1\/stelle$/);
  await expect(page.locator("[data-uc1-stelle]").first()).toContainText("Pensionsversicherungsanstalt");
  await expect(page.getByText("Einen Termin vereinbaren Sie direkt bei der Stelle.")).toBeVisible();
  await bild(page, "uc1-schritt-4-stelle");
  await axePruefen(page);
  await gateMessen(page, "/uc1/stelle (Beispiel)");
});

test("Fehler bei der Antwort auf eine Rückfrage steht an der Rückfrage", async ({ page }) => {
  let aufrufe = 0;
  await page.route("**/api/uc1/frage", (route) => {
    aufrufe += 1;
    return aufrufe === 1
      ? route.fulfill({ status: 200, json: PFLEGE.schritte[0]?.antwort })
      : route.fulfill({ status: 400, json: { fehler: "Bitte höchstens 1000 Zeichen." } });
  });
  await page.goto("/uc1");
  await page.getByLabel("Ihre Situation").fill("Meine Mutter kommt allein nicht mehr zurecht.");
  await page.getByRole("button", { name: "Senden" }).click();
  const feld = page.getByLabel("Ihre Antwort");
  await expect(feld).toBeFocused();
  await feld.fill("Sie bekommt eine Pension.");
  await page.getByRole("button", { name: "Antworten" }).click();
  await expect(page.locator('[data-uc1-antwort="rueckfrage"]')).toContainText("Bitte höchstens 1000 Zeichen.");
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
