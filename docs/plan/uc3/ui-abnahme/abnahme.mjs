// Lokale UI-Abnahme der UC3-Seiten gegen eine gefüllte UC3-Datenbank (#18 AC1/AC3, Review !51 Punkt 10).
// Die CI hat keine UC3-Datenbank und misst dort nur Leerzustände; diese Messung zeigt die gefüllten Seiten.
//
// Aufruf (Dev-Server mit UC3_DATABASE_URL auf der maßgeblichen DB, z. B. Port 3218):
//   node docs/plan/uc3/ui-abnahme/abnahme.mjs http://localhost:3218
// Schreibt je Route und Viewport einen Screenshot (JPEG) und messung.json in diesen Ordner.
//
// Gemessen je Seite: HTTP-Status, Konsolenfehler, die zwölf Schlüssel von measureSlop (web/tests/lib/slop-measure.js,
// root body), axe (WCAG 2 A/AA, critical und serious), waagrechter Überlauf von <main>, Zahlen ab 1.000 (ohne Datum)
// ohne Beleg-Chip im selben Abschnitt (section, header oder article) und Em-Dashes im sichtbaren Text.

import { writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const hier = path.dirname(fileURLToPath(import.meta.url));
const wurzel = path.resolve(hier, "../../../..");
const { chromium } = await import(path.join(wurzel, "node_modules/.pnpm/node_modules/playwright/index.mjs"));
const { default: AxeBuilder } = await import(path.join(wurzel, "web/node_modules/@axe-core/playwright/dist/index.mjs"));
const MESSSKRIPT = path.join(wurzel, "web/tests/lib/slop-measure.js");

const basis = process.argv[2] ?? "http://localhost:3218";
const SCHLUESSEL = [
  "kickersMono", "kickersCaps", "iconTiles", "shadowCards", "ghostCards", "gradientText",
  "glassBlur", "lightOrbs", "pulsingDecor", "sparklesNonAi", "emDashes", "questionHeadings",
];
const ROUTEN = [
  ["monatslaeufe", "/uc3"],
  ["lauf-2025-03", "/uc3/laeufe/2025-03"],
  ["lauf-2025-10", "/uc3/laeufe/2025-10"],
  ["berichte", "/uc3/berichte"],
  ["bericht-2025-10", "/uc3/berichte/2025-10"],
  ["regeln", "/uc3/berichte/regeln"],
  ["klassifikationen", "/uc3/klassifikationen"],
  ["freigaben", "/uc3/freigaben"],
  ["freigaben-erledigt", "/uc3/freigaben?reiter=erledigt"],
  ["fragen", "/uc3/fragen"],
  ["fragen-antwort", "/uc3/fragen", "Beschäftigte in Wien im März 2025"],
];
const VIEWPORTS = [
  ["1440", { width: 1440, height: 900 }],
  ["390", { width: 390, height: 844 }],
];

async function pruefen(page) {
  return page.evaluate(() => {
    const main = document.querySelector("main");
    // Zahlen ab 1.000 mit Tausenderpunkt, aber keine Datumsangaben wie 31.03.2025 (Punkt oder Ziffer davor/danach).
    const zahl = /(?<![\d.])\d{1,3}(?:\.\d{3})+(?![\d.])/;
    const ohneBeleg = [];
    if (main) {
      const gang = document.createTreeWalker(main, NodeFilter.SHOW_TEXT);
      for (let knoten = gang.nextNode(); knoten; knoten = gang.nextNode()) {
        const text = knoten.textContent ?? "";
        const el = knoten.parentElement;
        if (!zahl.test(text) || !el || el.closest("pre, code, details:not([open]), [data-baustein='herkunft']")) continue;
        if (el.offsetParent === null) continue;
        // Ein Beleg gilt für seinen Abschnitt (section/header/article), wie auf den Seiten gebaut.
        const abschnitt = el.closest("section, header, article") ?? main;
        if (!abschnitt.querySelector("[data-baustein='herkunft']")) ohneBeleg.push(text.trim().slice(0, 60));
      }
    }
    return {
      ueberlaufMain: main ? main.scrollWidth - main.clientWidth : null,
      ueberlaufSeite: document.documentElement.scrollWidth - window.innerWidth,
      ohneBeleg: ohneBeleg.slice(0, 10),
      ohneBelegAnzahl: ohneBeleg.length,
      emDashes: (document.body.innerText.match(/—/g) ?? []).length,
      chips: document.querySelectorAll("[data-baustein='herkunft']").length,
    };
  });
}

const browser = await chromium.launch();
const ergebnis = [];
for (const [name, route, frage] of ROUTEN) {
  for (const [vp, groesse] of VIEWPORTS) {
    const kontext = await browser.newContext({ viewport: groesse });
    const page = await kontext.newPage();
    const fehler = [];
    page.on("console", (m) => m.type() === "error" && fehler.push(m.text().slice(0, 160)));
    const antwort = await page.goto(basis + route, { waitUntil: "load" });
    await page.locator("main").first().waitFor({ state: "visible" });
    if (frage) {
      await page.getByRole("button", { name: frage }).first().click();
      await page.getByText("Ohne KI gerechnet").first().waitFor({ timeout: 90_000 });
    }
    await page.evaluate(async () => {
      await document.fonts.ready;
    });
    await page.addScriptTag({ path: MESSSKRIPT });
    const slop = await page.evaluate(() => measureSlop({ root: "body", samples: false }).counts);
    const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
    const axeSchwer = axe.violations.filter((v) => v.impact === "critical" || v.impact === "serious");
    const seite = await pruefen(page);
    const datei = `${name}-${vp}.jpg`;
    await page.screenshot({ path: path.join(hier, datei), type: "jpeg", quality: 70 });
    ergebnis.push({
      name,
      route,
      viewport: vp,
      status: antwort?.status() ?? null,
      konsolenfehler: fehler,
      slopTreffer: SCHLUESSEL.filter((k) => Number(slop[k] ?? 0) > 0).map((k) => `${k}=${slop[k]}`),
      axe: axeSchwer.map((v) => `${v.id} (${v.impact}, ${v.nodes.length})`),
      ...seite,
      screenshot: datei,
    });
    console.log(
      `${vp} ${route}${frage ? " +Frage" : ""}: ${antwort?.status()} slop=${ergebnis.at(-1).slopTreffer.length} ` +
        `axe=${axeSchwer.length} main+${seite.ueberlaufMain} ohneBeleg=${seite.ohneBelegAnzahl} chips=${seite.chips} ` +
        `konsole=${fehler.length}`,
    );
    await kontext.close();
  }
}
await browser.close();
writeFileSync(
  path.join(hier, "messung.json"),
  JSON.stringify({ basis, gemessen_am: new Date().toISOString(), ergebnis }, null, 2) + "\n",
);
