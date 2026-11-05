#!/usr/bin/env node
// Prüfbilder der Seite /praesentation für die UI-Regie (#59, #141): jede Szene im Endzustand bei 1920 × 1080,
// dazu die Handy-Ansicht 390 × 844 und die Druckansicht. Endzustand: Die Seite öffnet die nächste Szene und geht mit
// der Pfeiltaste eine zurück; die Navigation zeigt die vorige Szene dann mit allen Takten. Die letzte Szene wird
// mit Pfeil rechts bis zum Ende durchgeschaltet.
//
// Aufruf: BASIS_URL=<url> AUSGABE=<ordner> node docs/praesentation/werkzeug/praesentation_bilder.mjs
// Läuft wie aufnahme.mjs über dev-browser (eigener Browser e5-praesentation, headless) und beendet nur diesen.
// Nicht auf dem Vortragsrechner laufen lassen: Server und Browser gehören auf den Zweitrechner oder in die CI.

import { spawnSync } from "node:child_process";
import { copyFileSync, mkdirSync, readFileSync, statSync } from "node:fs";
import { join, resolve } from "node:path";

const BROWSER = "e5-praesentation";
const BASIS_URL = (process.env.BASIS_URL || "http://localhost:3000").replace(/\/+$/, "");
const AUSGABE = resolve(process.env.AUSGABE || "praesentation-bilder");
const SZENEN = Number(process.env.SZENEN || 10);

const DESKTOP = { width: 1920, height: 1080, deviceScaleFactor: 1 };
const HANDY = { width: 390, height: 844, deviceScaleFactor: 3, isMobile: true, hasTouch: true };

const auftraege = [
  ...Array.from({ length: SZENEN }, (_, i) =>
    i + 1 < SZENEN
      ? { name: `szene-${String(i + 1).padStart(2, "0")}-1920`, pfad: `/praesentation?folie=${i + 2}`, viewport: DESKTOP, taste: "ArrowLeft", mal: 1 }
      : { name: `szene-${String(i + 1).padStart(2, "0")}-1920`, pfad: `/praesentation?folie=${i + 1}`, viewport: DESKTOP, taste: "ArrowRight", mal: 6 },
  ),
  { name: "handy-hinweis-390", pfad: "/praesentation?folie=1", viewport: HANDY },
  { name: "handy-szene-05-390", pfad: "/praesentation?folie=5", viewport: HANDY },
  { name: "druck-1920", pfad: "/praesentation?folie=1", viewport: DESKTOP, druck: true },
];

// Browser-Skript: Ein Dialog bricht ab, nichts wird akzeptiert.
const browserSkript = `
const auftraege = ${JSON.stringify(auftraege)};
const basis = ${JSON.stringify(BASIS_URL)};
const ergebnisse = [];
for (const a of auftraege) {
  const page = await browser.getPage("e5-p-" + a.name);
  let dialog = null;
  page.on("dialog", async (d) => { dialog = d.type() + ": " + d.message(); await d.dismiss(); });
  await page.setViewport(a.viewport);
  await page.emulateMediaType(a.druck ? "print" : "screen");
  const antwort = await page.goto(basis + a.pfad, { waitUntil: "load", timeout: 30000 });
  await page.waitForNetworkIdle({ idleTime: 500, concurrency: 2, timeout: 10000 }).catch(() => {});
  await page.evaluate(() => document.fonts.ready);
  await new Promise((r) => setTimeout(r, 1500));
  for (let n = 0; n < (a.mal || 0); n++) {
    await page.keyboard.press(a.taste);
    await new Promise((r) => setTimeout(r, 2500));
  }
  if (a.mal) await new Promise((r) => setTimeout(r, 5000));
  if (dialog) throw new Error("Unerwarteter Dialog auf " + a.pfad + " (" + dialog + "), Abbruch");
  const daten = await page.screenshot({ type: "png", encoding: "base64", fullPage: Boolean(a.druck) });
  const path = await saveFile(a.name + ".png", Buffer.from(daten, "base64"));
  ergebnisse.push({ name: a.name, pfad: a.pfad, status: antwort ? antwort.status() : null, path });
}
console.log("ERGEBNIS " + JSON.stringify(ergebnisse));
`;

function devBrowser(args, input) {
  return spawnSync("dev-browser", args, { input, encoding: "utf8", timeout: 330000 });
}

let exitCode = 0;
try {
  const lauf = devBrowser(["-b", BROWSER, "--headless", "--timeout", "300"], browserSkript);
  process.stderr.write(lauf.stderr || "");
  const zeile = (lauf.stdout || "").split("\n").find((l) => l.startsWith("ERGEBNIS "));
  if (lauf.status !== 0 || !zeile) {
    process.stdout.write(lauf.stdout || "");
    throw new Error(`dev-browser endete mit Status ${lauf.status}`);
  }
  mkdirSync(AUSGABE, { recursive: true });
  for (const e of JSON.parse(zeile.slice("ERGEBNIS ".length))) {
    if (e.status !== null && e.status >= 400) throw new Error(`${e.name}: HTTP ${e.status}`);
    const ziel = join(AUSGABE, `${e.name}.png`);
    copyFileSync(e.path, ziel);
    const kopf = readFileSync(ziel).subarray(0, 24);
    if (kopf.subarray(0, 8).toString("hex") !== "89504e470d0a1a0a") throw new Error(`${ziel}: kein PNG`);
    console.log(`${e.name} ${e.pfad}: ${kopf.readUInt32BE(16)}x${kopf.readUInt32BE(20)}, ${statSync(ziel).size} Bytes`);
  }
} catch (fehler) {
  console.error(`praesentation_bilder: ${fehler.message}`);
  exitCode = 1;
} finally {
  devBrowser(["stop", BROWSER]);
}
process.exit(exitCode);
