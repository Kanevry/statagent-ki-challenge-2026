#!/usr/bin/env node
/**
 * Erzeugt die Punktdichte-Karte Österreichs für die Landing-Szene.
 *
 * Aufruf: node web/landing/werkzeug/karte-erzeugen.mjs <laender_geo.json>
 * Eingabe: Bundesländer-Grenzen als GeoJSON (MultiPolygon je Land, Eigenschaft `iso` = Code 1..9).
 *   Quelle: ginseng666/GeoJSON-TopoJSON-Austria, 2021/simplified-99.5/laender_995_geo.json,
 *   CC BY 4.0 Flooh Perlot; Original CC BY 4.0 Statistik Austria, data.statistik.gv.at.
 * Ausgabe: web/public/landing/oesterreich-punkte.bin und oesterreich-meta.json (Format: web/landing/szene/vertrag.ts).
 *
 * Deterministisch: fester Seed, keine Uhrzeit, keine Abhängigkeiten. Zwei Läufe ergeben byte-gleiche Dateien.
 */
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const N = 60_000;
const SEED = 0x5a7a6e;
const KANDIDATEN = 3; // Mitchell best-candidate: ruhigere Verteilung als reiner Zufall
const DP_EPS = 0.0015;
const COS_BREITE = Math.cos((47.6 * Math.PI) / 180);

// Verhältnisse am 31.08.2024 je Bundesland (Beispielbericht Tab2, gleich wie web/landing/daten/fakten.ts).
const ANZAHL = { 1: 11_265, 2: 22_385, 3: 64_505, 4: 68_141, 5: 26_968, 6: 53_901, 7: 35_437, 8: 16_839, 9: 90_799 };
const NAME = {
  1: "Burgenland", 2: "Kärnten", 3: "Niederösterreich", 4: "Oberösterreich", 5: "Salzburg",
  6: "Steiermark", 7: "Tirol", 8: "Vorarlberg", 9: "Wien",
};

function mulberry32(a) {
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const eingabe = process.argv[2];
if (!eingabe) {
  console.error("Aufruf: node web/landing/werkzeug/karte-erzeugen.mjs <laender_geo.json>");
  process.exit(2);
}
const geo = JSON.parse(readFileSync(eingabe, "utf8"));

// Projektion: äquirektangulär, x = lon·cos(47,6°), y = −lat.
const projiziere = ([lon, lat]) => [lon * COS_BREITE, -lat];

/** Länder: code → Ringe (projiziert); Löcher bleiben Ringe, Punkt-in-Polygon mit Gerade-Ungerade-Regel. */
const laender = new Map();
for (const f of geo.features) {
  const code = Number(f.properties.iso);
  if (!(code in ANZAHL)) throw new Error(`Unbekannter Code ${f.properties.iso} (${f.properties.name})`);
  const polys = f.geometry.type === "MultiPolygon" ? f.geometry.coordinates : [f.geometry.coordinates];
  const ringe = [];
  const aussen = [];
  for (const poly of polys) {
    poly.forEach((ring, i) => {
      const p = ring.map(projiziere);
      ringe.push(p);
      if (i === 0) aussen.push(p);
    });
  }
  laender.set(code, { code, ringe, aussen });
}
if (laender.size !== 9) throw new Error(`Erwartet 9 Bundesländer, gefunden ${laender.size}`);

// Gesamt-Bounding-Box und Normierung auf 0..1.
let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
for (const l of laender.values())
  for (const r of l.aussen)
    for (const [x, y] of r) {
      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
    }
const breite = maxX - minX;
const hoehe = maxY - minY;
const norm = ([x, y]) => [(x - minX) / breite, (y - minY) / hoehe];
for (const l of laender.values()) {
  l.ringe = l.ringe.map((r) => r.map(norm));
  l.aussen = l.aussen.map((r) => r.map(norm));
  let bx0 = 1, bx1 = 0, by0 = 1, by1 = 0;
  for (const r of l.aussen)
    for (const [x, y] of r) {
      bx0 = Math.min(bx0, x); bx1 = Math.max(bx1, x); by0 = Math.min(by0, y); by1 = Math.max(by1, y);
    }
  l.bbox = [bx0, by0, bx1, by1];
}
const seitenverhaeltnis = breite / hoehe;

function innen(ringe, x, y) {
  let drin = false;
  for (const r of ringe) {
    for (let i = 0, j = r.length - 1; i < r.length; j = i++) {
      const [xi, yi] = r[i];
      const [xj, yj] = r[j];
      if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) drin = !drin;
    }
  }
  return drin;
}

// Zielzahlen je Land: Largest-Remainder, Summe exakt N.
const summe = Object.values(ANZAHL).reduce((a, b) => a + b, 0);
const codes = Object.keys(ANZAHL).map(Number);
const roh = codes.map((c) => ({ c, v: (N * ANZAHL[c]) / summe }));
const ziel = new Map(roh.map(({ c, v }) => [c, Math.floor(v)]));
let rest = N - [...ziel.values()].reduce((a, b) => a + b, 0);
for (const { c } of [...roh].sort((a, b) => (b.v % 1) - (a.v % 1) || a.c - b.c)) {
  if (rest-- <= 0) break;
  ziel.set(c, ziel.get(c) + 1);
}

// Punkte je Land: Mitchell best-candidate im Seitenverhältnis-korrigierten Raum, Gitter-Hash für Nachbarn.
const zufall = mulberry32(SEED);
const punkteJeLand = new Map();
for (const code of codes) {
  const l = laender.get(code);
  const anzahl = ziel.get(code);
  const [bx0, by0, bx1, by1] = l.bbox;
  const zelle = Math.sqrt(((bx1 - bx0) * seitenverhaeltnis * (by1 - by0)) / Math.max(anzahl, 1)) * 2;
  const gitter = new Map();
  const schluessel = (gx, gy) => gx * 100_003 + gy;
  const pts = [];
  const zufallsPunkt = () => {
    for (;;) {
      const x = bx0 + zufall() * (bx1 - bx0);
      const y = by0 + zufall() * (by1 - by0);
      if (innen(l.ringe, x, y)) return [x, y];
    }
  };
  const abstand2 = (x, y) => {
    const gx = Math.floor((x * seitenverhaeltnis) / zelle);
    const gy = Math.floor(y / zelle);
    let best = Infinity;
    for (let dx = -1; dx <= 1; dx++)
      for (let dy = -1; dy <= 1; dy++) {
        const liste = gitter.get(schluessel(gx + dx, gy + dy));
        if (!liste) continue;
        for (const [px, py] of liste) {
          const ddx = (px - x) * seitenverhaeltnis;
          const ddy = py - y;
          const d = ddx * ddx + ddy * ddy;
          if (d < best) best = d;
        }
      }
    return best;
  };
  for (let i = 0; i < anzahl; i++) {
    let wahl = null;
    let wahlD = -1;
    for (let k = 0; k < KANDIDATEN; k++) {
      const [x, y] = zufallsPunkt();
      const d = abstand2(x, y);
      if (d > wahlD) {
        wahlD = d;
        wahl = [x, y];
      }
    }
    pts.push(wahl);
    const s = schluessel(Math.floor((wahl[0] * seitenverhaeltnis) / zelle), Math.floor(wahl[1] / zelle));
    const liste = gitter.get(s);
    if (liste) liste.push(wahl);
    else gitter.set(s, [wahl]);
  }
  // Reihenfolge innerhalb des Landes mischen (Fisher-Yates), damit jedes Präfix das ganze Land abdeckt.
  for (let i = pts.length - 1; i > 0; i--) {
    const j = Math.floor(zufall() * (i + 1));
    [pts[i], pts[j]] = [pts[j], pts[i]];
  }
  punkteJeLand.set(code, pts);
}

// Geschichtete Reihenfolge: in jedem Schritt das Land mit dem größten Rückstand zu seinem Anteil.
const anteil = new Map(codes.map((c) => [c, ziel.get(c) / N]));
const genommen = new Map(codes.map((c) => [c, 0]));
const xs = new Uint16Array(N);
const ys = new Uint16Array(N);
const bls = new Uint8Array(N);
const q = (v) => Math.max(0, Math.min(65535, Math.round(v * 65535)));
for (let i = 0; i < N; i++) {
  let bester = codes[0];
  let besterRueck = -Infinity;
  for (const c of codes) {
    if (genommen.get(c) >= ziel.get(c)) continue;
    const rueck = anteil.get(c) * (i + 1) - genommen.get(c);
    if (rueck > besterRueck) {
      besterRueck = rueck;
      bester = c;
    }
  }
  const [x, y] = punkteJeLand.get(bester)[genommen.get(bester)];
  genommen.set(bester, genommen.get(bester) + 1);
  xs[i] = q(x);
  ys[i] = q(y);
  bls[i] = bester;
}

// Binärdatei: Uint32 N, N×Uint16 x, N×Uint16 y, N×Uint8 bl (little-endian).
const buf = Buffer.alloc(4 + N * 2 + N * 2 + N);
buf.writeUInt32LE(N, 0);
for (let i = 0; i < N; i++) {
  buf.writeUInt16LE(xs[i], 4 + i * 2);
  buf.writeUInt16LE(ys[i], 4 + N * 2 + i * 2);
  buf.writeUInt8(bls[i], 4 + N * 4 + i);
}

// Beschriftungsanker: flächengewichteter Schwerpunkt des größten Außenrings, sonst nächster Kartenpunkt.
function flaeche(r) {
  let a = 0;
  for (let i = 0, j = r.length - 1; i < r.length; j = i++) a += r[j][0] * r[i][1] - r[i][0] * r[j][1];
  return a / 2;
}
function schwerpunkt(r) {
  let cx = 0, cy = 0;
  const a = flaeche(r);
  for (let i = 0, j = r.length - 1; i < r.length; j = i++) {
    const f = r[j][0] * r[i][1] - r[i][0] * r[j][1];
    cx += (r[j][0] + r[i][0]) * f;
    cy += (r[j][1] + r[i][1]) * f;
  }
  return [cx / (6 * a), cy / (6 * a)];
}
const r4 = (v) => Math.round(v * 10_000) / 10_000;
const label = (l) => {
  const groesster = [...l.aussen].sort((a, b) => Math.abs(flaeche(b)) - Math.abs(flaeche(a)))[0];
  let [cx, cy] = schwerpunkt(groesster);
  if (!innen(l.ringe, cx, cy)) {
    const pts = punkteJeLand.get(l.code);
    let best = pts[0];
    let bd = Infinity;
    for (const [x, y] of pts) {
      const d = (x - cx) ** 2 + (y - cy) ** 2;
      if (d < bd) {
        bd = d;
        best = [x, y];
      }
    }
    [cx, cy] = best;
  }
  return [r4(cx), r4(cy)];
};

// Douglas-Peucker für die Grenzlinien.
function dp(pts, eps) {
  if (pts.length < 3) return pts;
  const [ax, ay] = pts[0];
  const [bx, by] = pts[pts.length - 1];
  let idx = -1;
  let maxD = 0;
  const lx = (bx - ax) * seitenverhaeltnis;
  const ly = by - ay;
  const len = Math.hypot(lx, ly) || 1e-12;
  for (let i = 1; i < pts.length - 1; i++) {
    const px = (pts[i][0] - ax) * seitenverhaeltnis;
    const py = pts[i][1] - ay;
    const d = Math.abs(lx * py - ly * px) / len;
    if (d > maxD) {
      maxD = d;
      idx = i;
    }
  }
  if (maxD <= eps) return [pts[0], pts[pts.length - 1]];
  return [...dp(pts.slice(0, idx + 1), eps).slice(0, -1), ...dp(pts.slice(idx), eps)];
}
/** Geschlossener Ring: am vom Start entferntesten Punkt teilen, sonst fällt die Sehne auf Länge 0. */
function dpRing(r, eps) {
  let weit = 1;
  let wd = -1;
  for (let i = 1; i < r.length - 1; i++) {
    const d = ((r[i][0] - r[0][0]) * seitenverhaeltnis) ** 2 + (r[i][1] - r[0][1]) ** 2;
    if (d > wd) {
      wd = d;
      weit = i;
    }
  }
  return [...dp(r.slice(0, weit + 1), eps).slice(0, -1), ...dp(r.slice(weit), eps)];
}
const grenzen = [];
for (const code of codes) {
  for (const r of laender.get(code).aussen) {
    const v = dpRing(r, DP_EPS);
    if (v.length >= 4) grenzen.push(v.flatMap(([x, y]) => [r4(x), r4(y)]));
  }
}

const meta = {
  quelle:
    "Statistik Austria, data.statistik.gv.at (OGD, Gemeindegrenzen 2021), bearbeitet von Flooh Perlot (ginseng666/GeoJSON-TopoJSON-Austria)",
  lizenz: "CC BY 4.0",
  seitenverhaeltnis: Math.round(seitenverhaeltnis * 10_000) / 10_000,
  n: N,
  laender: codes.map((c) => ({
    code: c,
    name: NAME[c],
    label: label(laender.get(c)),
    anteil: Math.round((ziel.get(c) / N) * 1_000_000) / 1_000_000,
  })),
  grenzen,
};

const ziel_dir = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "public", "landing");
mkdirSync(ziel_dir, { recursive: true });
writeFileSync(join(ziel_dir, "oesterreich-punkte.bin"), buf);
writeFileSync(join(ziel_dir, "oesterreich-meta.json"), JSON.stringify(meta));
console.log(
  `oesterreich-punkte.bin: ${buf.length} Bytes, N=${N}; oesterreich-meta.json: ${JSON.stringify(meta).length} Bytes; ` +
    `Seitenverhältnis ${meta.seitenverhaeltnis}; Grenzlinien ${grenzen.length}`,
);
