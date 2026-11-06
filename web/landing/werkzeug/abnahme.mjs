#!/usr/bin/env node
/**
 * Abnahme der Landingpage gegen einen laufenden Server: Screenshots Desktop/Mobil entlang der Scroll-Erzählung,
 * measureSlop je Größe, optional Reduced-Motion-Bild. Üblicher Aufruf über abnahme-build.sh, direkt z. B.:
 *   cd web && pnpm build && (pnpm exec next start -p 3999 &) && \
 *     node landing/werkzeug/abnahme.mjs http://localhost:3999 ../docs/landing/v2 /pfad/zu/slop-measure.js
 *
 * Argumente: <basis-url> <ausgabe-ordner> <pfad zu slop-measure.js (impeccable-Katalog, Apache-2.0)>
 * Ausgabe: PNGs und abnahme.json (volles measureSlop-Ergebnis je Variante unter `slop`, die Zähler unter
 * `slop.counts`; Konsolenfehler) im Ausgabe-Ordner. Exit 1, sobald ein Zähler über 0 liegt.
 */
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { chromium } from "@playwright/test";

const [basis = "http://localhost:3999", ausgabe = "../docs/landing/v1", slopPfad] = process.argv.slice(2);
mkdirSync(ausgabe, { recursive: true });
const slopQuelle = slopPfad ? readFileSync(slopPfad, "utf8") : null;

const GROESSEN = [
  { name: "desktop", width: 1440, height: 900, mobil: false },
  { name: "mobil", width: 390, height: 844, mobil: true },
];
// Fortschritt in der Geschichte (web/landing/sektionen/Geschichte.tsx).
const FORTSCHRITTE = [0, 0.12, 0.37, 0.63, 0.88, 1];
const ABSCHNITTE = ["ansatz", "datenfehler", "use-cases", "team"];

const warte = (ms) => new Promise((r) => setTimeout(r, ms));
const bericht = { basis, zeit: new Date().toISOString(), groessen: {} };

const browser = await chromium.launch({ args: ["--enable-gpu", "--use-angle=metal", "--ignore-gpu-blocklist"] });
try {
  for (const g of GROESSEN) {
    for (const reduziert of [false, true]) {
      const kontext = await browser.newContext({
        viewport: { width: g.width, height: g.height },
        deviceScaleFactor: g.mobil ? 3 : 2,
        isMobile: g.mobil,
        hasTouch: g.mobil,
        reducedMotion: reduziert ? "reduce" : "no-preference",
      });
      const seite = await kontext.newPage();
      const fehler = [];
      seite.on("console", (m) => m.type() === "error" && fehler.push(m.text()));
      seite.on("pageerror", (e) => fehler.push(String(e)));
      seite.on("response", (r) => r.status() >= 400 && fehler.push(`HTTP ${r.status()} ${r.url()}`));
      await seite.goto(basis + "/", { waitUntil: "load", timeout: 60_000 });
      await warte(1800);
      const praefix = `${g.name}${reduziert ? "-reduziert" : ""}`;

      if (!reduziert) {
        // Sticky-Strecke: erste <section> mit data-szene oder das erste Element mit position: sticky.
        const strecke = await seite.evaluate(() => {
          // Weiches Einrasten aus: Die Bilder sollen genau an den Fortschritten unten entstehen.
          document.documentElement.style.scrollSnapType = "none";
          const s = document.querySelector("[data-szene]") ?? document.querySelector("main section");
          if (!s) return null;
          const r = s.getBoundingClientRect();
          return { top: r.top + window.scrollY, hoehe: r.height };
        });
        for (const p of FORTSCHRITTE) {
          if (strecke) {
            const y = strecke.top + p * Math.max(0, strecke.hoehe - g.height);
            await seite.evaluate((yy) => window.scrollTo(0, yy), y);
          }
          await warte(900);
          await seite.screenshot({ path: join(ausgabe, `${praefix}-szene-${String(Math.round(p * 100)).padStart(3, "0")}.png`) });
        }
      }
      for (const id of ABSCHNITTE) {
        const da = await seite.evaluate((i) => {
          const el = document.getElementById(i);
          if (!el) return false;
          el.scrollIntoView({ block: "start" });
          return true;
        }, id);
        if (!da) continue;
        await warte(700);
        await seite.screenshot({ path: join(ausgabe, `${praefix}-${id}.png`) });
      }

      let slop = null;
      if (slopQuelle) {
        await seite.evaluate(() => window.scrollTo(0, 0));
        await warte(300);
        await seite.addScriptTag({ content: slopQuelle });
        // Alle Abschnitte einmal durchscrollen, damit Einblendungen sichtbar sind, dann messen.
        await seite.evaluate(async () => {
          for (let y = 0; y < document.body.scrollHeight; y += window.innerHeight * 0.8) {
            window.scrollTo(0, y);
            await new Promise((r) => setTimeout(r, 120));
          }
        });
        await warte(600);
        slop = await seite.evaluate(() =>
          // eslint-disable-next-line no-undef
          measureSlop({ root: "body", samples: true }),
        );
      }
      bericht.groessen[praefix] = { slop, konsolenfehler: fehler };
      await kontext.close();
    }
  }
} finally {
  await browser.close();
}
writeFileSync(join(ausgabe, "abnahme.json"), JSON.stringify(bericht, null, 2));
let trefferGesamt = 0;
for (const [k, v] of Object.entries(bericht.groessen)) {
  const counts = v.slop?.counts ?? {};
  const treffer = Object.entries(counts).filter(([, n]) => typeof n === "number" && n > 0);
  trefferGesamt += treffer.length;
  console.log(`${k}: Konsolenfehler ${v.konsolenfehler.length}; measureSlop Treffer: ${JSON.stringify(Object.fromEntries(treffer))}`);
}
if (trefferGesamt > 0) process.exitCode = 1;
