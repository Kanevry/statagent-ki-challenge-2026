/**
 * /uc1 SV KI-Lotse (#35) im Browser, je Projekt der Konfiguration (desktop 1440×900, mobil 390×844).
 * Das Replay läuft ohne Netz: jeder Aufruf unter /api/ wird abgebrochen. Läuft in der CI, nicht lokal.
 */
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Locator, type Page } from "@playwright/test";
import { leistungenTitel } from "../components/uc1/leistungen";

const hier = path.dirname(fileURLToPath(import.meta.url));
const MESSSKRIPT = path.join(hier, "lib", "slop-measure.js");
type Traeger = { leistung: string | null; name: string; fundstelle: string | null; zitat?: string | null };
const PFLEGE = JSON.parse(readFileSync(path.join(hier, "../components/uc1/fixtures/pflege.json"), "utf8")) as {
  schritte: Array<{
    eingabe: { text: string };
    antwort: {
      aussagen: Array<{ zitat: string }>;
      modell: string | null;
      provider: string | null;
      naechste_schritte: string[];
      traeger: Traeger[];
      leistungen: string[];
      rueckfrage: string | null;
      rueckfrage_optionen?: Array<{ text: string; antwort: string }>;
    } & Record<string, unknown>;
  }>;
};
// Alles Erwartete kommt aus der Aufnahme: ein Tausch der Fixture braucht hier keine Änderung.
const ZITATE = PFLEGE.schritte.flatMap((s) => s.antwort.aussagen.map((a) => a.zitat));
const LETZTE = PFLEGE.schritte.at(-1)?.antwort;
if (!LETZTE) throw new Error("Aufnahme ohne Schritte");
const AUFNAHME_MODELL = `mit ${[LETZTE.provider, LETZTE.modell].filter(Boolean).join(", ")}`;
const ERSTE = PFLEGE.schritte[0]?.antwort;
if (!ERSTE) throw new Error("Aufnahme ohne Rückfrage");
const OPTIONEN = ERSTE.rueckfrage_optionen ?? [];
/** Überschrift der Leistungen, wie die Seite sie bildet: „Pflegegeld kommt …“, „Zwei Leistungen kommen für Sie in Frage“. */
const LEISTUNGEN_TITEL = leistungenTitel(LETZTE.leistungen);
/** Zuständigkeiten mit Leistung und Fundstelle. */
const ZUSTAENDIG = LETZTE.traeger.filter(
  (t): t is Traeger & { leistung: string; fundstelle: string } => Boolean(t.leistung && t.fundstelle),
);
const TERMIN = "Einen Termin vereinbaren Sie direkt bei der Stelle.";

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

/** Tippziel mindestens 44 px hoch. */
async function tippziel(ziel: Locator): Promise<void> {
  expect((await ziel.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(44);
}

/** Drei Schritte, keine Tab-Leiste mit „Stelle“ oder „Anliegen“. */
async function fuehrungPruefen(page: Page): Promise<void> {
  await expect(page.getByRole("list", { name: "Ihre Schritte" }).getByRole("listitem")).toHaveText([
    "1 Situation",
    "2 Leistungen",
    "3 Antrag",
  ]);
  await expect(page.getByRole("link", { name: /^(Stelle|Anliegen)$/ })).toHaveCount(0);
}

/** Die KI-Kennzeichnung als eine ruhige Zeile: Aufnahme, Datum, Modell, erfundene Personenangaben. */
async function kennzeichnungPruefen(ki: Locator): Promise<void> {
  await expect(ki).toContainText("KI-Antwort, geprüft gegen die Quellen.");
  await expect(ki).toContainText("Aufgezeichnet am");
  await expect(ki).toContainText(AUFNAHME_MODELL);
  await expect(ki).toContainText("Personenangaben erfunden.");
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
  await expect(page.getByText("Geburtsdatum, Adresse und Telefonnummer blendet der Lotse aus, wenn er sie erkennt. Namen bleiben stehen.", { exact: false })).toBeVisible();
  await bild(page, "uc1-leer");
  await axePruefen(page);
  await gateMessen(page, "/uc1 leer");
});

test("/uc1?beispiel=pflege spielt ohne Netz in drei Schritten bis zum Antrag mit Stelle", async ({ page }) => {
  await page.route("**/api/**", (route) => route.abort());
  await page.goto("/uc1?beispiel=pflege");
  const hoehe = page.viewportSize()?.height ?? 0;

  // Schritt 1, Rückfrage: kurze Frage, Antwortknöpfe aus der Aufnahme, Freitext als Alternative.
  const rueckfrage = page.locator('[data-uc1-antwort="rueckfrage"]');
  await expect(rueckfrage).toHaveCount(1);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Eine Angabe fehlt noch");
  await expect(page.getByTestId("uc1-situation-kurz")).toContainText(PFLEGE.schritte[0]?.eingabe.text ?? "");
  await expect(page.getByLabel("Ihre Situation")).toHaveCount(0);
  await fuehrungPruefen(page);
  expect(OPTIONEN.length, "Aufnahme mit rueckfrage_optionen").toBeGreaterThan(0);
  const gruppe = page.getByRole("group", { name: "Wer zahlt die Pension?" });
  await expect(gruppe).toBeVisible();
  // Die Erklärung hinter dem ersten Satz steht nicht mehr da, die Knöpfe zeigen sie.
  await expect(rueckfrage).not.toContainText("Sie können auch sagen");
  for (const option of OPTIONEN) {
    const knopf = gruppe.getByRole("button", { name: option.text });
    await expect(knopf).toBeVisible();
    await tippziel(knopf);
  }
  await expect(page.getByLabel("Oder selbst schreiben")).toBeVisible();
  // Während die Aufnahme läuft, geht nichts live hinaus.
  await expect(page.getByRole("button", { name: "Antworten" })).toHaveAttribute("aria-disabled", "true");
  await kennzeichnungPruefen(rueckfrage.getByTestId("uc1-ki"));
  await bild(page, "uc1-schritt-1-rueckfrage");

  // Schritt 2, Leistungen: konkrete Überschrift, der Fokus steht darauf.
  await expect(page.locator('[data-uc1-antwort="antwort"]')).toHaveCount(1, { timeout: 15_000 });
  const titel = page.getByRole("heading", { level: 1 });
  await expect(titel).toHaveText(LEISTUNGEN_TITEL);
  await expect(titel).toBeFocused();
  await fuehrungPruefen(page);
  for (const id of LETZTE.leistungen) await expect(page.locator(`[data-uc1-leistung="${id}"]`)).toBeVisible();
  // Gestrichen: „Sie: …“ und „So geht es weiter“.
  await expect(page.locator('[data-uc1-antwort="antwort"]').getByText(/^Sie: /)).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "So geht es weiter" })).toHaveCount(0);
  // Begründung mit Beleg in der Karte der ersten Leistung.
  const erste = page.locator(`[data-uc1-leistung="${LETZTE.leistungen[0]}"]`);
  await expect(erste.locator("[data-uc1-begruendung] [data-baustein='herkunft']")).toHaveCount(1);
  // Hauptaktion über dem Falz, auch auf 390 × 844.
  const antragKnopf = page.getByRole("button", { name: "Antrag vorbereiten" }).first();
  const box = await antragKnopf.boundingBox();
  expect((box?.y ?? Infinity) + (box?.height ?? 0), "Antrag vorbereiten im ersten Bildschirm").toBeLessThanOrEqual(hoehe);
  await tippziel(antragKnopf);
  // Zuständige Stelle mit Fundstelle und Terminsatz; ein Chip nur mit Zitat zu genau dieser Stelle.
  const stelle = page.getByRole("region", { name: "Zuständige Stelle" });
  await expect(stelle).toContainText("Pensionsversicherungsanstalt");
  await expect(stelle).toContainText(TERMIN);
  for (const t of ZUSTAENDIG) {
    const zeile = stelle.locator(`[data-uc1-stelle-leistung="${t.leistung}"]`);
    await expect(zeile).toHaveCount(1);
    await expect(zeile.locator('[data-baustein="herkunft"]')).toHaveCount(t.zitat ? 1 : 0);
    if (!t.zitat) await expect(zeile).not.toContainText(t.fundstelle);
  }
  // Quellen hinter „Details“, Zusammenfassung 44 px.
  const quellen = page.locator("[data-uc1-quellen]");
  const zusammenfassung = quellen.locator("summary");
  await expect(zusammenfassung).toHaveText("Details: Quellen");
  await tippziel(zusammenfassung);
  await zusammenfassung.click();
  await expect(quellen.getByRole("listitem")).toHaveCount(LETZTE.aussagen.length);
  // KI-Kennzeichnung an jeder Antwort (frühere eingeklappt, aber vorhanden).
  await expect(page.getByTestId("uc1-ki")).toHaveCount(PFLEGE.schritte.length);
  await kennzeichnungPruefen(page.locator('[data-uc1-antwort="antwort"]').getByTestId("uc1-ki"));
  await expect(page.getByTestId("uc1-aufnahme")).toHaveCount(0);

  // Beleg über den gemeinsamen HerkunftChip: aufklappen zeigt das Zitat wörtlich.
  const chip = page.locator('[data-baustein="herkunft"]').first().getByRole("button", { name: /Zitat ansehen/ });
  await chip.click();
  await expect(chip).toHaveAttribute("aria-expanded", "true");
  const zitat = page.locator('[data-baustein="herkunft"] blockquote').first();
  await expect(zitat).toBeVisible();
  const text = (await zitat.textContent()) ?? "";
  expect(ZITATE).toContain(text.trim());
  await bild(page, "uc1-schritt-2-leistungen");
  await axePruefen(page);
  await gateMessen(page, "/uc1?beispiel=pflege");

  // „ändern“ bringt das Eingabefeld mit der Situation zurück.
  await page.getByRole("button", { name: "ändern" }).click();
  await expect(page.getByLabel("Ihre Situation")).toHaveValue(PFLEGE.schritte[0]?.eingabe.text ?? "");
  await page.getByRole("button", { name: "Zurück zur Antwort" }).click();

  // Schritt 3: Antrag aus der Aufnahme, ohne Netz, mit Stelle rechts.
  await page.getByRole("button", { name: "Antrag vorbereiten" }).first().click();
  await expect(page).toHaveURL(/\/uc1\/antrag$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Pflegegeld: Antrag vorbereitet");
  await fuehrungPruefen(page);
  await kennzeichnungPruefen(page.getByTestId("uc1-ki"));
  await expect(page.getByRole("cell", { name: "Maria" })).toBeVisible();
  await expect(page.getByText("Diese Angaben stammen aus Ihrem Gespräch.")).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Herkunft" })).toHaveCount(0);
  await expect(page.getByText("bitte ergänzen")).toHaveCount(0);
  await expect(page.locator("ol > [data-uc1-offen]").first()).toBeVisible();
  // Offene Punkte nach Formularseite: genau ein Beleg je Seitengruppe, keine Pillen-Kette je Punkt.
  const offen = page.getByRole("region", { name: "Das ergänzen Sie selbst" });
  const seitenGruppen = await offen.locator("[data-uc1-offen-seite]").count();
  expect(seitenGruppen).toBeGreaterThan(0);
  await expect(offen.getByText("Zitat ansehen")).toHaveCount(seitenGruppen);
  await expect(page.getByText("Abgeschickt wird nichts. Sie prüfen, unterschreiben und senden selbst.")).toBeVisible();
  await expect(page.locator("[data-uc1-unterlagen] summary")).toHaveText("Details: Unterlagen");
  const antragStelle = page.getByRole("region", { name: "Zuständige Stelle" }).filter({ visible: true });
  await expect(antragStelle).toHaveCount(1);
  await expect(antragStelle).toContainText("Pensionsversicherungsanstalt");
  await expect(antragStelle).toContainText(TERMIN);
  await expect(page.getByRole("link", { name: "Weiter zur zuständigen Stelle" })).toHaveCount(0);
  // „Entwurf prüfen“: ab md rechts und beim Scrollen fest, mobil direkt unter der Überschrift (vor der Tabelle).
  const pruefen = page.getByRole("heading", { name: "Entwurf prüfen" });
  const aside = page.getByRole("complementary", { name: "Prüfen und zuständige Stelle" });
  const breit = (page.viewportSize()?.width ?? 0) >= 768;
  expect(await aside.evaluate((el) => getComputedStyle(el).position)).toBe(breit ? "sticky" : "static");
  const pruefenY = (await pruefen.boundingBox())?.y ?? Infinity;
  const tabelleY = (await page.getByRole("table").boundingBox())?.y ?? 0;
  if (!breit) expect(pruefenY, "Entwurf prüfen vor der Tabelle").toBeLessThan(tabelleY);
  // Im Replay gibt es kein PDF und nichts, was etwas abschickt.
  await expect(page.getByRole("link", { name: "Antrag als PDF speichern" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /abschicken|absenden|einreichen/i })).toHaveCount(0);
  await bild(page, "uc1-schritt-3-antrag");
  await axePruefen(page);
  await gateMessen(page, "/uc1/antrag (Beispiel)");

  // Prüfung des Entwurfs: erst nach Vor- und Nachnamen gilt er als geprüft. „Maria Muster“ lehnt die Namensregel
  // ab (Platzhalter „muster“), deshalb ein echter Name. Feld und Knopf sind mindestens 44 px hoch.
  const stand = page.getByTestId("uc1-entwurf-stand");
  await expect(stand).toHaveText("Entwurf nicht geprüft");
  await expect(page.getByText("Ihr Name steht nur auf diesem Entwurf und gilt in dieser Sitzung")).toBeVisible();
  const name = page.getByLabel("Ihr Vor- und Nachname");
  const markieren = page.getByRole("button", { name: "Entwurf als geprüft markieren" });
  for (const ziel of [name, markieren]) await tippziel(ziel);
  await name.fill("Team");
  await expect(markieren).toBeDisabled();
  await name.fill("Maria Huber");
  await markieren.click();
  await expect(stand).toContainText("Entwurf geprüft von Maria Huber");
  await expect(page.getByRole("button", { name: "Prüfung zurücknehmen" })).toBeVisible();
  await bild(page, "uc1-schritt-3-geprueft");
  await axePruefen(page);
  await gateMessen(page, "/uc1/antrag (geprüft)");
});

test("Ein Antwortknopf der Rückfrage schickt seine Antwort als Nachricht", async ({ page }) => {
  const gesendet: string[] = [];
  await page.route("**/api/uc1/frage", (route) => {
    gesendet.push((route.request().postDataJSON() as { text: string }).text);
    return gesendet.length === 1
      ? route.fulfill({ status: 200, json: ERSTE })
      : route.fulfill({ status: 200, json: LETZTE });
  });
  await page.goto("/uc1");
  await page.getByLabel("Ihre Situation").fill("Meine Mutter kommt allein nicht mehr zurecht.");
  await page.getByRole("button", { name: "Senden" }).click();
  const option = OPTIONEN[0];
  if (!option) throw new Error("Aufnahme ohne rueckfrage_optionen");
  await page.getByRole("button", { name: option.text }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(LEISTUNGEN_TITEL);
  expect(gesendet[1]).toBe(option.antwort);
});

test("Fehler bei der Antwort auf eine Rückfrage steht an der Rückfrage", async ({ page }) => {
  let aufrufe = 0;
  await page.route("**/api/uc1/frage", (route) => {
    aufrufe += 1;
    return aufrufe === 1
      ? route.fulfill({ status: 200, json: ERSTE })
      : route.fulfill({ status: 400, json: { fehler: "Bitte höchstens 1000 Zeichen." } });
  });
  await page.goto("/uc1");
  await page.getByLabel("Ihre Situation").fill("Meine Mutter kommt allein nicht mehr zurecht.");
  await page.getByRole("button", { name: "Senden" }).click();
  // Mit Antwortknöpfen steht der Fokus auf der Überschrift; der Freitext bleibt die Alternative.
  await expect(page.getByRole("heading", { level: 1 })).toBeFocused();
  const feld = page.getByLabel(OPTIONEN.length > 0 ? "Oder selbst schreiben" : "Ihre Antwort");
  // Der Knopf ist aktiv und prüft beim Klick: leer abgeschickt kommt ein Satz statt eines grauen Knopfs.
  await expect(page.getByRole("button", { name: "Antworten" })).not.toHaveAttribute("aria-disabled", "true");
  await page.getByRole("button", { name: "Antworten" }).click();
  await expect(page.locator('[data-uc1-antwort="rueckfrage"]')).toContainText("Bitte schreiben Sie eine kurze Antwort.");
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

test("Unterseiten liefern 200 mit ehrlichem Leerzustand, Stelle und Anliegen leiten um", async ({ page }) => {
  for (const pfad of ["/uc1/leistungen", "/uc1/antrag"]) {
    const antwort = await page.goto(pfad);
    expect(antwort?.status(), pfad).toBe(200);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await fuehrungPruefen(page);
    await gateMessen(page, pfad);
  }
  await page.goto("/uc1/stelle");
  await expect(page).toHaveURL(/\/uc1\/antrag$/);
  await page.goto("/uc1/anliegen");
  await expect(page).toHaveURL(/\/uc1$/);
});
