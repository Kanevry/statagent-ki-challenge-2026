#!/usr/bin/env node
// Nimmt die Screenshots SC01–SC12 über dev-browser auf (GitLab #88).
//
// Aufruf: BASIS_URL=<url> node docs/praesentation/werkzeug/aufnahme.mjs
// dev-browser-Skripte laufen in einem VM-Kontext ohne process/fs; dieses Node-Skript baut
// deshalb das Browser-Skript mit eingebetteten Zielen, lässt es über stdin laufen und kopiert
// die Bilder aus ~/.dev-browser/v1/tmp ins Repo. Danach wird nur der eigene Browser beendet.

import { spawnSync } from "node:child_process";
import { copyFileSync, mkdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const BROWSER = "e5-screens";
const BASIS_URL = (process.env.BASIS_URL || "http://localhost:3000").replace(/\/+$/, "");
const SCREENS = resolve(dirname(fileURLToPath(import.meta.url)), "..", "screens");

// Bild, Route, Viewports. SC11 zeigt den gemeinsamen Einstieg (UC4) mit dem Wechsel der Use Cases im App-Kopf.
const ZIELE = [{ bild: "SC11", route: "/uc4" }];
const VIEWPORTS = [
  { art: "desktop", width: 1920, height: 1080, deviceScaleFactor: 1 },
  { art: "mobil", width: 390, height: 844, deviceScaleFactor: 3, isMobile: true, hasTouch: true },
];

function zielpfad(bild, art) {
  return art === "desktop" ? join(SCREENS, `${bild}.png`) : join(SCREENS, "mobil", `${bild}-mobil.png`);
}

const auftraege = ZIELE.flatMap((z) => VIEWPORTS.map((v) => ({ ...z, viewport: v, url: BASIS_URL + z.route })));

// Browser-Skript: Dialog-Handler vor jeder Navigation; ein Dialog bricht ab, nichts wird akzeptiert.
const browserSkript = `
const auftraege = ${JSON.stringify(auftraege)};
const ergebnisse = [];
for (const a of auftraege) {
  const page = await browser.getPage("e5-" + a.bild + "-" + a.viewport.art);
  let dialog = null;
  page.on("dialog", async (d) => { dialog = d.type() + ": " + d.message(); await d.dismiss(); });
  await page.setViewport(a.viewport);
  const antwort = await page.goto(a.url, { waitUntil: "load", timeout: 30000 });
  // Offene Verbindungen (Streaming, Polling) verhindern völlige Netzruhe: kurz warten, nicht blockieren.
  await page.waitForNetworkIdle({ idleTime: 500, concurrency: 2, timeout: 10000 }).catch(() => {});
  await page.evaluate(() => document.fonts.ready);
  await new Promise((r) => setTimeout(r, 800));
  if (dialog) throw new Error("Unerwarteter Dialog auf " + a.route + " (" + dialog + "), Abbruch");
  const name = a.bild + "-" + a.viewport.art + ".png";
  // page.shot rechnet auf CSS-Pixel herunter; die native Aufnahme behält deviceScaleFactor.
  const daten = await page.screenshot({ type: "png", encoding: "base64" });
  const path = await saveFile(name, Buffer.from(daten, "base64"));
  ergebnisse.push({ bild: a.bild, art: a.viewport.art, status: antwort ? antwort.status() : null, path });
}
console.log("ERGEBNIS " + JSON.stringify(ergebnisse));
`;

function devBrowser(args, input) {
  return spawnSync("dev-browser", args, { input, encoding: "utf8", timeout: 150000 });
}

let exitCode = 0;
try {
  const lauf = devBrowser(["-b", BROWSER, "--headless", "--timeout", "120"], browserSkript);
  process.stderr.write(lauf.stderr || "");
  const zeile = (lauf.stdout || "").split("\n").find((l) => l.startsWith("ERGEBNIS "));
  if (lauf.status !== 0 || !zeile) {
    process.stdout.write(lauf.stdout || "");
    throw new Error(`dev-browser endete mit Status ${lauf.status}`);
  }
  for (const e of JSON.parse(zeile.slice("ERGEBNIS ".length))) {
    if (e.status !== null && e.status >= 400) throw new Error(`${e.bild} ${e.art}: HTTP ${e.status}`);
    const ziel = zielpfad(e.bild, e.art);
    mkdirSync(dirname(ziel), { recursive: true });
    copyFileSync(e.path, ziel);
    const kopf = readFileSync(ziel).subarray(0, 24);
    if (kopf.subarray(0, 8).toString("hex") !== "89504e470d0a1a0a") throw new Error(`${ziel}: kein PNG`);
    const [breite, hoehe] = [kopf.readUInt32BE(16), kopf.readUInt32BE(20)];
    console.log(`${e.bild} ${e.art}: ${breite}x${hoehe}, ${statSync(ziel).size} Bytes -> ${ziel}`);
  }
} catch (fehler) {
  console.error(`aufnahme: ${fehler.message}`);
  exitCode = 1;
} finally {
  devBrowser(["stop", BROWSER]);
}
process.exit(exitCode);
