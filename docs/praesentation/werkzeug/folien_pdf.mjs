#!/usr/bin/env node
// Folien als fertige PDF-Datei zum Kopieren auf den USB-Stick: Druckansicht von /praesentation, eine Seite je Folie,
// jede Folie im Endzustand, 1920 × 1080. Die Datei braucht weder Netz noch Browser-App zum Zeigen.
//
// Aufruf aus web/ (dort liegt @playwright/test), auf dem Zweitrechner, nie auf dem Vortragsrechner:
//   BASIS_URL=<url> AUSGABE=<datei.pdf> node ../docs/praesentation/werkzeug/folien_pdf.mjs
//   BASIS_URL=<url> AUSGABE=<datei.pdf> AUSWAHL=1,2,3,5,6,9,10 node ../docs/praesentation/werkzeug/folien_pdf.mjs
// AUSWAHL nennt die Foliennummern, die in die Datei sollen (Finale-Fassung). Ohne AUSWAHL kommen alle Folien hinein.
// Ausgaben gehören nach docs/praesentation/export/ (dort ignoriert) oder außerhalb des Repos.

import { mkdirSync, statSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, resolve } from "node:path";

const require = createRequire(join(process.cwd(), "package.json"));
const { chromium } = require("@playwright/test");

const BASIS_URL = (process.env.BASIS_URL || "http://localhost:3000").replace(/\/+$/, "");
const AUSGABE = resolve(process.env.AUSGABE || "folien.pdf");
const AUSWAHL = (process.env.AUSWAHL || "")
  .split(",")
  .map((s) => s.trim())
  .filter(Boolean);

const browser = await chromium.launch({ headless: true });
try {
  // Reduzierte Bewegung von Anfang an: Sonst druckt die Datei Sätze, die sich noch tippen.
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, reducedMotion: "reduce" });
  page.on("dialog", async (d) => {
    await d.dismiss();
    throw new Error(`Unerwarteter Dialog: ${d.message()}`);
  });
  // BASIS_URL ist die Adresse der App, oder direkt die Seite einer Fassung (…/praesentation/management).
  const seite = /\/praesentation(\/[^/?#]+)?$/.test(BASIS_URL) ? BASIS_URL : `${BASIS_URL}/praesentation`;
  await page.goto(`${seite}?folie=1`, { waitUntil: "networkidle", timeout: 120000 });
  await page.locator("[data-folie]").first().waitFor({ timeout: 60000 });
  await page.emulateMedia({ media: "print" });
  await page.evaluate(() => document.fonts.ready);

  const szenen = await page.evaluate((auswahl) => {
    const alle = [...document.querySelectorAll("[data-nr]")];
    if (auswahl.length > 0) {
      for (const s of alle) if (!auswahl.includes(s.getAttribute("data-nr"))) s.remove();
    }
    // Nur die Folien drucken: Alles neben dem Folienrahmen weg (Kopf der App), kein Abstand um ihn herum,
    // und nach der letzten Folie kein Seitenumbruch, sonst folgt eine leere Seite.
    let knoten = document.querySelector("[data-folie]");
    while (knoten && knoten !== document.documentElement) {
      const eltern = knoten.parentElement;
      if (eltern) for (const k of eltern.children) if (k !== knoten) k.style.setProperty("display", "none", "important");
      for (const [name, wert] of [["margin", "0"], ["padding", "0"], ["gap", "0"], ["min-height", "0"], ["display", "block"]]) {
        knoten.style.setProperty(name, wert, "important");
      }
      knoten = eltern;
    }
    const uebrig = document.querySelectorAll("[data-nr]");
    uebrig[uebrig.length - 1]?.style.setProperty("break-after", "auto", "important");
    return uebrig.length;
  }, AUSWAHL);
  if (szenen === 0 || (AUSWAHL.length > 0 && szenen !== AUSWAHL.length)) {
    throw new Error(`Auswahl passt nicht: ${szenen} Folien gefunden, ${AUSWAHL.length} verlangt`);
  }

  mkdirSync(dirname(AUSGABE), { recursive: true });
  await page.pdf({ path: AUSGABE, preferCSSPageSize: true, printBackground: true });
  console.log(`${AUSGABE}: ${szenen} Folien, ${statSync(AUSGABE).size} Bytes`);
} finally {
  await browser.close();
}
