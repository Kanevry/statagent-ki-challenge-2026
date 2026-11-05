#!/usr/bin/env node
// Backup-Video der Demo (#90, Rückfallstufe 3): D1 Qualitätsbericht, D2 Rückblick auf die drei Aufträge, D3 drei geprüfte
// Datenanfragen. Nimmt mit Playwright (recordVideo) auf und wandelt mit ffmpeg in MP4 (H.264, 1920 × 1080).
//
// Aufruf aus web/ (dort liegt @playwright/test):
//   BASIS_URL=<url> AUSGABE=<datei.mp4> node ../docs/praesentation/werkzeug/backup_video.mjs
// Läuft auf dem Zweitrechner, nie auf dem Vortragsrechner. Ändert keine Daten: nur lesen, die Datenanfragen
// lesen die Datenbank. Die Kennzeichnung „Aufzeichnung vom …“ steht von der ersten bis zur letzten Sekunde im Bild.
// Stimmt eine Antwort nicht mit der Sollzahl überein, bricht die Aufnahme ab, statt eine falsche Zahl aufzunehmen.

import { spawnSync } from "node:child_process";
import { mkdtempSync, readdirSync, statSync } from "node:fs";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const require = createRequire(join(process.cwd(), "package.json"));
const { chromium } = require("@playwright/test");

const BASIS_URL = (process.env.BASIS_URL || "http://localhost:3000").replace(/\/+$/, "");
const AUSGABE = resolve(process.env.AUSGABE || "backup-demo.mp4");
const FFMPEG = process.env.FFMPEG || "ffmpeg";
const ZEIT = new Intl.DateTimeFormat("de-AT", {
  timeZone: "Europe/Vienna",
  day: "numeric",
  month: "long",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
}).format(new Date());
const KENNZEICHEN = `Aufzeichnung vom ${ZEIT}`;

// Sollzahlen aus dem Fragenkatalog (F14, F23); Prüfung im Team, #74.
const FRAGEN = [
  {
    text: "Zeigen Sie mir die Zeitreihe der Beschäftigten, jeweils zum Monatsletzten.",
    soll: "392.236",
    zeile: "D3 Datenanfrage 1: Zeitreihe am Monatsletzten, August 2024 beginnt mit 392.236",
  },
  {
    text: "Wie viele Männer und Frauen sind im August 2024 je Bundesland beschäftigt?",
    soll: "211.603",
    zeile: "D3 Datenanfrage 2: Männer 211.603, Frauen 180.633, je Bundesland",
  },
  {
    text: "Wie hoch ist die Fluktuation je Wirtschaftsbereich im Oktober 2024?",
    soll: "3,42",
    zeile: "D3 Datenanfrage 3: Fluktuation im Oktober 2024, 3,42 %",
  },
];

const warte = (ms) => new Promise((r) => setTimeout(r, ms));

// Kennzeichnung und Untertitel als feste Ebenen über der Seite; sie überstehen jede Navigation.
function ebenen(kennzeichen) {
  const bau = () => {
    if (document.getElementById("aufz-kennzeichen")) return;
    const k = document.createElement("div");
    k.id = "aufz-kennzeichen";
    k.textContent = kennzeichen;
    k.style.cssText =
      "position:fixed;top:16px;right:16px;z-index:2147483647;background:#0b1117;color:#f4d35e;" +
      "font:600 22px/1.2 system-ui,sans-serif;padding:10px 16px;border-radius:8px;pointer-events:none";
    const u = document.createElement("div");
    u.id = "aufz-zeile";
    u.style.cssText =
      "position:fixed;left:24px;bottom:24px;z-index:2147483647;background:rgba(11,17,23,.92);color:#fff;" +
      "font:500 26px/1.3 system-ui,sans-serif;padding:12px 18px;border-radius:8px;max-width:1500px;pointer-events:none";
    u.textContent = window.__aufzZeile || "";
    const s = document.createElement("style");
    s.textContent = "nextjs-portal{display:none!important}";
    document.body.append(k, u, s);
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bau);
  else bau();
}

async function zeile(page, text) {
  await page.evaluate((t) => {
    window.__aufzZeile = t;
    const u = document.getElementById("aufz-zeile");
    if (u) u.textContent = t;
  }, text);
}

async function oeffne(page, pfad, text) {
  await page.addInitScript((t) => {
    window.__aufzZeile = t;
  }, text);
  const antwort = await page.goto(BASIS_URL + pfad, { waitUntil: "load", timeout: 30000 });
  if (!antwort || antwort.status() >= 400) throw new Error(`${pfad}: HTTP ${antwort ? antwort.status() : "?"}`);
  await page.waitForLoadState("networkidle", { timeout: 10000 }).catch(() => {});
  if ((await page.locator("body").innerText()).includes("Die Zahlen ließen sich gerade nicht lesen")) {
    throw new Error(`${pfad}: Fehlerseite (Zahlen nicht lesbar)`);
  }
  await zeile(page, text);
}

async function rolle(page, schritte, ms) {
  for (let i = 0; i < schritte; i++) {
    await page.mouse.wheel(0, 420);
    await warte(ms);
  }
}

const ordner = mkdtempSync(join(tmpdir(), "e5-video-"));
const browser = await chromium.launch({ headless: true });
let ok = false;
try {
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 1,
    recordVideo: { dir: ordner, size: { width: 1920, height: 1080 } },
  });
  await context.addInitScript(ebenen, KENNZEICHEN);
  const page = await context.newPage();
  page.on("dialog", async (d) => {
    await d.dismiss();
    throw new Error(`Unerwarteter Dialog: ${d.message()}`);
  });
  await page.mouse.move(960, 540);

  // D1 Qualitätsbericht Oktober 2025 (F11, F17)
  await oeffne(page, "/uc3/berichte/2025-10", "D1 Qualitätsbericht Oktober 2025: Die Lieferung ist unvollständig, der Monat ist angehalten");
  await warte(6000);
  await rolle(page, 6, 4000);

  // D2 Rückblick: die drei Aufträge der Aufgabe (Vorschläge 24 bis 26), jeder mit Namen freigegeben (F26)
  await oeffne(page, "/uc3/freigaben", "D2 Rückblick: die drei Aufträge der Aufgabe, jeder mit Vor- und Nachnamen freigegeben");
  await page.locator("#erledigt-titel").waitFor({ timeout: 20000 });
  for (const id of [24, 25, 26]) {
    await page.locator(`a[href="/uc3/freigaben/${id}"]`).first().waitFor({ timeout: 20000 });
  }
  await warte(6000);
  await rolle(page, 3, 3000);

  // D2 Vorschlag 24 (Auftrag 1) im Detail, Zahlen vorher und nachher (F19)
  await oeffne(page, "/uc3/freigaben/24", "D2 Änderung per Sprache: Vorschlag 24, Zahlen vorher und nachher, freigegeben mit Namen");
  await warte(6000);
  await rolle(page, 6, 4000);

  // D3 drei geprüfte Datenanfragen
  await oeffne(page, "/uc3/fragen", "D3 Fragen an die Daten: Das Programm rechnet ohne KI und zeigt die Abfrage");
  await warte(4000);
  for (const f of FRAGEN) {
    await zeile(page, f.zeile);
    const feld = page.locator('form[aria-label="Frage an die Daten"] input, form[aria-label="Frage an die Daten"] textarea').first();
    await feld.click();
    await feld.fill("");
    await feld.pressSequentially(f.text, { delay: 35 });
    await warte(800);
    await page.locator('form[aria-label="Frage an die Daten"] button[type="submit"]').click();
    const ergebnis = page.locator('section[aria-labelledby="ergebnis-titel"]');
    const soll = ergebnis.getByText(f.soll, { exact: false });
    await soll.first().waitFor({ state: "attached", timeout: 45000 });
    // Steht die Sollzahl nur im ganzen Antwortsatz unter „Details“ (etwa die Summen von Männern und Frauen),
    // klappt die Aufnahme „Details“ auf, damit die Zahl im Bild ist.
    if ((await soll.locator("visible=true").count()) === 0) {
      await ergebnis.locator("summary", { hasText: /^Details$/ }).last().click();
    }
    await soll.locator("visible=true").first().waitFor({ timeout: 15000 });
    await warte(9000);
    await rolle(page, 2, 2500);
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" }));
    await warte(1500);
  }
  await zeile(page, "Ende der Aufzeichnung");
  await warte(3000);
  await context.close();
  ok = true;
} finally {
  await browser.close();
}

if (ok) {
  const webm = readdirSync(ordner).find((n) => n.endsWith(".webm"));
  if (!webm) throw new Error("kein Video aufgenommen");
  const lauf = spawnSync(
    FFMPEG,
    ["-y", "-loglevel", "error", "-i", join(ordner, webm), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "24",
      "-preset", "medium", "-movflags", "+faststart", "-an", AUSGABE],
    { stdio: "inherit" },
  );
  if (lauf.status !== 0) throw new Error(`ffmpeg endete mit ${lauf.status}`);
  console.log(`${AUSGABE}: ${statSync(AUSGABE).size} Bytes, ${KENNZEICHEN}`);
}
