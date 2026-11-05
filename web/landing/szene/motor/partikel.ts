/**
 * Partikel-Puffer für die GPU: je Partikel eine Position je Schritt plus Zustand. Reine Funktion
 * ohne three.js; wird bei Größenänderung oder neuen Kartendaten neu geschrieben, nie pro Bild.
 *
 * Reihenfolge im Puffer: Säule 2024-08, 2024-09, … 2026-07 (je Säule von unten nach oben), danach
 * die hohlen Ringe der fehlenden Befunde (fd-fehlen, teil-lieferung).
 *
 * Schritt 3: Jedes Säulen-Partikel bekommt einen Kartenpunkt (Präfix der Kartendatei in
 * Pufferreihenfolge, 2024-08 zuerst), außer der gelben Gruppe „ohne Bundesland“. Schritt 4: alle
 * Kartenpartikel bilden die Punkt-Balken je Bundesland.
 */
import type { KartenDaten } from "../vertrag";
import { GRUPPE, planePartikel, raster, type BefundId, type PartikelPlan, type Rechteck, type SzeneLayout } from "./layout";
import { zufallsquelle } from "./zufall";

/** info.x */
export const ART = { normal: 0, markiert: 1, fehlt: 2 } as const;
/** info.y: was das Partikel in Schritt 3/4 tut (Ringe blenden aus) */
export const ZIEL = { weg: 0, karte: 1, unbekannt: 2 } as const;

/** Obergrenze der Ringe (Puffer der Zufallswerte) */
const RINGE_MAX = 2048;

export interface PartikelPuffer {
  /** Partikel plus Ringe */
  anzahl: number;
  /** Säulen-Partikel (= PARTIKEL[variante]) */
  partikel: number;
  /** vec2 Schritt 1 (Säule) */
  position: Float32Array;
  /** vec2 Endzustand Schritt 2 */
  pruef: Float32Array;
  /** vec2 Schritt 3 */
  karte: Float32Array;
  /** vec2 Schritt 4 */
  tabelle: Float32Array;
  /** vec4 stabile Zufallswerte 0..1 (Verzögerung, Bogen) */
  zufall: Float32Array;
  /** vec4 (art, ziel, x der Säulenmitte, Höhe in der Säule 0..1) */
  info: Float32Array;
  /** float: Ringe = Durchmesser in CSS-Pixeln; sonst 0 */
  dichte: Float32Array;
  /** vec2 Kartenpunkt: (Größe in CSS-Pixeln, Deckkraft); in dichten Zellen (Wien) klein und blass */
  stil: Float32Array;
  /** Kontrolle: Kartenpartikel je Bundesland-Code */
  kartenJeLand: Map<number, number>;
}

/** Stabile Zufallswerte: hängen nur von der Variante ab, nicht von der Größe. */
interface Saat {
  plan: PartikelPlan;
  zufall: Float32Array;
  streuung: Float32Array;
  /** Index (in Säule 0) → Befund und Rang */
  befundInSaeule0: Map<number, { id: BefundId; rang: number }>;
  /** Index (in Säule 0) → Rang in der Gruppe „ohne Bundesland“ (Schritt 3/4), inkl. der markierten */
  unbekanntInSaeule0: Map<number, number>;
}

const saatCache = new Map<string, Saat>();

function saat(plan: PartikelPlan): Saat {
  const vorhanden = saatCache.get(plan.variante);
  if (vorhanden) return vorhanden;
  const max = plan.gesamt + RINGE_MAX;
  const z = zufallsquelle(0x0a5e_2024);
  const zufall = new Float32Array(max * 4);
  const streuung = new Float32Array(max * 2);
  for (let i = 0; i < max * 4; i++) zufall[i] = z();
  for (let i = 0; i < max * 2; i++) streuung[i] = z() - 0.5;
  // Befunde in 2024-08: verstreute Zeilen der Säule, feste Auswahl
  const c0 = plan.saeulen[0];
  const idx = Array.from({ length: c0 }, (_, i) => i);
  for (let i = idx.length - 1; i > 0; i--) {
    const j = Math.floor(z() * (i + 1));
    [idx[i], idx[j]] = [idx[j], idx[i]];
  }
  const befundInSaeule0 = new Map<number, { id: BefundId; rang: number }>();
  const unbekanntInSaeule0 = new Map<number, number>();
  let k = 0;
  for (const b of plan.befunde.filter((b) => b.lieferungIndex === 0 && b.art === "markiert")) {
    for (let r = 0; r < b.partikel; r++) {
      befundInSaeule0.set(idx[k], { id: b.id, rang: r });
      if (b.id === "bl-oenace-leer") unbekanntInSaeule0.set(idx[k], r);
      k++;
    }
  }
  // Auflösung der Karte: die Gruppe „ohne Bundesland“ wächst in Schritt 3 um weitere Partikel aus 2024-08
  for (let r = unbekanntInSaeule0.size; r < plan.unbekanntPunkte && k < idx.length; r++) unbekanntInSaeule0.set(idx[k++], r);
  const s = { plan, zufall, streuung, befundInSaeule0, unbekanntInSaeule0 };
  saatCache.set(plan.variante, s);
  return s;
}

/** Punkt `rang` in einem gefüllten Raster mit `spalten` Spalten und Abstand `a` ab links oben. */
function rasterPunkt(r: Rechteck, rang: number, spalten: number, a: number): [number, number] {
  return [r.x + ((rang % spalten) + 0.5) * a, r.y + (Math.floor(rang / spalten) + 0.5) * a];
}

/** Punkt `rang` in einem Raster mit `nx` Spalten, das das Rechteck mit `n` Punkten füllt. */
function flaechenPunkt(r: Rechteck, rang: number, n: number, nx: number): [number, number] {
  const ny = Math.max(1, Math.ceil(n / nx));
  const gx = rang % nx;
  const gy = Math.floor(rang / nx);
  return [r.x + ((gx + 0.5) / nx) * r.breite, r.y + ((gy + 0.5) / ny) * r.hoehe];
}

export function bauePartikel(layout: SzeneLayout, karte: KartenDaten): PartikelPuffer {
  const plan = planePartikel(layout.variante);
  const s = saat(plan);
  const ringe = Math.min(
    RINGE_MAX,
    layout.befunde.reduce((a, b) => a + b.ringe, 0),
  );
  const n = plan.gesamt + ringe;
  const position = new Float32Array(n * 2);
  const pruef = new Float32Array(n * 2);
  const kartePos = new Float32Array(n * 2);
  const tabelle = new Float32Array(n * 2);
  const info = new Float32Array(n * 4);
  const dichte = new Float32Array(n);
  const stil = new Float32Array(n * 2);

  const befundAnker = new Map(layout.befunde.map((b) => [b.id, b]));
  const abstand = GRUPPE[layout.variante].abstand;
  const dubletten = plan.befunde.find((b) => b.id === "volldubletten")!;
  const dublAnker = befundAnker.get("volldubletten")!;

  const setze = (arr: Float32Array, i: number, x: number, y: number) => {
    arr[i * 2] = x;
    arr[i * 2 + 1] = y;
  };

  // Kartenpartikel in Pufferreihenfolge (2024-08 zuerst), Gruppe „ohne Bundesland“ nach Rang
  const kartenIndizes: number[] = [];
  const kartenJeSaeule: number[] = [];
  const unbekanntIndizes: number[] = new Array(plan.unbekanntPunkte);

  let i = 0;
  layout.saeulen.forEach((sa, si) => {
    const c = plan.saeulen[si];
    const hz = sa.unten - sa.oben;
    const sb = sa.rechts - sa.links;
    const { nx, ny } = raster(c, sb, hz);
    const zw = sb / nx;
    const zh = hz / ny;
    const dublStart = c - dubletten.partikel;
    kartenJeSaeule[si] = 0;
    for (let k = 0; k < c; k++, i++) {
      const gx = k % nx;
      const gy = Math.floor(k / nx);
      const x = sa.links + (gx + 0.5 + s.streuung[i * 2] * 0.35) * zw;
      const y = sa.unten - (gy + 0.5 + s.streuung[i * 2 + 1] * 0.35) * zh;
      setze(position, i, x, y);
      let art: number = ART.normal;
      let ziel: number = ZIEL.karte;
      let px = x;
      let py = y;
      if (si === 0) {
        const b = s.befundInSaeule0.get(k);
        if (b) {
          art = ART.markiert;
          const a = befundAnker.get(b.id)!;
          [px, py] = rasterPunkt(a.gruppe, b.rang, a.gruppeSpalten, abstand);
        }
        const u = s.unbekanntInSaeule0.get(k);
        if (u !== undefined) {
          ziel = ZIEL.unbekannt;
          unbekanntIndizes[u] = i;
        }
      } else if (si === dubletten.lieferungIndex && k >= dublStart) {
        art = ART.markiert;
        [px, py] = rasterPunkt(dublAnker.gruppe, k - dublStart, dublAnker.gruppeSpalten, abstand);
      }
      if (ziel === ZIEL.karte) {
        kartenIndizes.push(i);
        kartenJeSaeule[si]++;
      }
      setze(pruef, i, px, py);
      info[i * 4] = art;
      info[i * 4 + 1] = ziel;
      info[i * 4 + 2] = sa.x;
      info[i * 4 + 3] = (gy + 0.5) / ny;
    }
  });

  // Ringe der fehlenden Befunde: Hohlraum auf der Säule → kompakte Gruppe; blenden in Schritt 3 aus
  for (const a of layout.befunde.filter((x) => x.art === "fehlt")) {
    const sa = layout.saeulen.find((x) => x.lieferung === a.lieferung)!;
    for (let r = 0; r < a.ringe && i < n; r++, i++) {
      const [qx, qy] = flaechenPunkt(a.quelle, r, a.ringe, a.quelleSpalten);
      const [gx, gy] = rasterPunkt(a.gruppe, r, a.gruppeSpalten, a.gruppe.breite / a.gruppeSpalten);
      setze(position, i, qx, qy);
      setze(pruef, i, gx, gy);
      setze(kartePos, i, gx, gy);
      setze(tabelle, i, gx, gy);
      dichte[i] = a.ringPx;
      info[i * 4] = ART.fehlt;
      info[i * 4 + 1] = ZIEL.weg;
      info[i * 4 + 2] = sa.x;
      info[i * 4 + 3] = 0.5;
    }
  }

  // Karte: genau das Präfix der geschichteten Stichprobe (so viele Punkte wie Kartenpartikel).
  // 2024-08 nimmt den Anfang des Präfixes und legt damit das ganze Land grob an; die übrigen
  // Säulen füllen je einen West-Ost-Streifen (links → Westen), damit der Strom geordnet fließt.
  const k = layout.karte;
  const kartenJeLand = new Map<number, number>();
  const jeLandIndizes = new Map<number, number[]>();
  const punktVon = new Int32Array(kartenIndizes.length);
  const fuehrend = kartenJeSaeule[0] ?? 0;
  for (let j = 0; j < fuehrend; j++) punktVon[j] = j;
  const kx = (q: number) => karte.x[q % karte.n];
  const ky = (q: number) => karte.y[q % karte.n];
  const rest = Array.from({ length: kartenIndizes.length - fuehrend }, (_, r) => fuehrend + r).sort((p, q) => kx(p) - kx(q));
  let versatz = 0;
  let start = fuehrend;
  for (let si = 1; si < kartenJeSaeule.length; si++) {
    const m = kartenJeSaeule[si];
    const punkteS = rest.slice(versatz, versatz + m).sort((p, q) => ky(p) - ky(q));
    const teile = Array.from({ length: m }, (_, r) => start + r).sort(
      (p, q) => position[kartenIndizes[p] * 2 + 1] - position[kartenIndizes[q] * 2 + 1],
    );
    teile.forEach((t, r) => (punktVon[t] = punkteS[r]));
    versatz += m;
    start += m;
  }
  kartenIndizes.forEach((pi, j) => {
    const q = punktVon[j] % karte.n;
    setze(kartePos, pi, k.x + karte.x[q] * k.breite, k.y + karte.y[q] * k.hoehe);
    const code = karte.bl[q];
    kartenJeLand.set(code, (kartenJeLand.get(code) ?? 0) + 1);
    let liste = jeLandIndizes.get(code);
    if (!liste) jeLandIndizes.set(code, (liste = []));
    liste.push(pi);
  });

  // Punktgröße und Deckkraft aus der örtlichen Dichte: überall gleich große Punkte; wo sie sich
  // stapeln (Wien), kleiner und so blass, dass die Fläche satt, aber nicht heller als Mint wird.
  const zelle = 5;
  const zaehler = new Map<number, number>();
  const zellKey = (pi: number) =>
    Math.floor(kartePos[pi * 2] / zelle) * 8192 + Math.floor(kartePos[pi * 2 + 1] / zelle);
  for (const pi of kartenIndizes) {
    const key = zellKey(pi);
    zaehler.set(key, (zaehler.get(key) ?? 0) + 1);
  }
  const dichten = [...zaehler.values()].sort((a, b) => a - b);
  const median = (dichten[Math.floor(dichten.length / 2)] ?? 1) / (zelle * zelle);
  const basis = Math.min(2.2, Math.max(1.0, 0.8 / Math.sqrt(median)));
  for (const pi of kartenIndizes) {
    const rho = (zaehler.get(zellKey(pi)) ?? 1) / (zelle * zelle);
    const d = Math.min(1, Math.sqrt((2.5 * median) / rho));
    const groesse = basis * (0.72 + 0.28 * d);
    const flaeche = (Math.PI / 4) * groesse * groesse;
    stil[pi * 2] = groesse;
    stil[pi * 2 + 1] = Math.min(0.8, Math.max(0.06, 1.25 / (rho * flaeche)));
  }

  // Tabelle: je Land von West nach Ost in die Punkt-Balken, damit der Fluss geordnet bleibt
  const t = layout.tabelle;
  const pa = t.punktAbstand;
  for (const zeile of t.zeilen) {
    const liste = (jeLandIndizes.get(zeile.code) ?? []).slice().sort((p, q) => kartePos[p * 2] - kartePos[q * 2]);
    liste.forEach((pi, r) => {
      const spalte = Math.floor(r / t.punktReihen);
      const reihe = r % t.punktReihen;
      setze(tabelle, pi, t.x0 + (spalte + 0.5) * pa, zeile.oben + (reihe + 0.5) * pa);
    });
  }

  // Gruppe „ohne Bundesland“: neben der Karte, dann als zehnter Balken
  const ug = k.unbekannt;
  const ugSpalten = Math.max(1, Math.round(ug.breite / abstand));
  unbekanntIndizes.forEach((pi, r) => {
    if (pi === undefined) return;
    const [ax, ay] = rasterPunkt(ug, r, ugSpalten, abstand);
    setze(kartePos, pi, ax, ay);
    const spalte = Math.floor(r / t.punktReihen);
    const reihe = r % t.punktReihen;
    setze(tabelle, pi, t.unbekannt.x + (spalte + 0.5) * pa, t.unbekannt.y + (reihe + 0.5) * pa);
  });

  return {
    anzahl: n,
    partikel: plan.gesamt,
    position,
    pruef,
    karte: kartePos,
    tabelle,
    zufall: s.zufall.subarray(0, n * 4),
    info,
    dichte,
    stil,
    kartenJeLand,
  };
}
