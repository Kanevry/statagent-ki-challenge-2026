/**
 * Zeitplan der Übergänge, in Anteilen des jeweiligen Schritts (s = 0..1 innerhalb von SCHRITTE).
 * Der Vertex-Shader nutzt dieselben Zahlen (shader.ts setzt sie als #define); die CPU braucht sie
 * nur für Prüflinie und Linien-Deckkraft.
 */
import { SCHRITTE } from "../vertrag";

export const ZEITPLAN = {
  /** Schritt 2: Prüflinie läuft von links nach rechts */
  scanVon: 0.03,
  scanBis: 0.48,
  /** Schritt 2: markierte Partikel ziehen in ihre Gruppen */
  gruppeVon: 0.55,
  gruppeBis: 0.88,
  /** Schritt 3: Säule 2024-08 führt den Strom in die Karte an (Start, Ende des Starts) */
  fuehrungVon: 0.02,
  fuehrungStreu: 0.14,
  /** Schritt 3: übrige Säulen folgen gestaffelt von links nach rechts */
  folgeVon: 0.16,
  folgeStaffel: 0.3,
  folgeStreu: 0.08,
  /** Schritt 3: Dauer des Flugs je Partikel */
  flug: 0.26,
  /** Schritt 3: Ringe der fehlenden Befunde blenden aus */
  ringeAusBis: 0.14,
  /** Schritt 4: Karte ordnet sich zu Balken */
  tabelleVon: 0.04,
  tabelleBis: 0.6,
} as const;

/**
 * Phasen der DOM-Beschriftungen in Anteilen des Schritts: sichtbar erst, wenn die Partikel ruhen,
 * weg, sobald sie wieder aufbrechen. Die Seite (HeroSzene) setzt danach `data-marken`.
 */
export const MARKEN = {
  /** Befund-Gruppen ruhen ab s2 = gruppeBis */
  befundeAb: 0.9,
  befundeBisS3: 0.02,
  /** Karte steht ab s3 ≈ folgeVon + folgeStaffel + folgeStreu + flug */
  karteAb: 0.82,
  karteBisS4: 0.04,
  /** Balken stehen ab s4 ≈ tabelleBis */
  tabelleAb: 0.62,
} as const

/**
 * Fortschrittswerte, an denen die Szene je Schritt ruht (alle Übergänge des Schritts fertig).
 * Für `reduziert` und Standbilder: die Seite setzt p auf diese Werte.
 */
export const RUHE_P = {
  lieferungen: 0.12,
  pruefen: 0.48,
  zaehlen: 0.73,
  belegen: 0.96,
} as const;

const schritt = (id: (typeof SCHRITTE)[number]["id"]) => SCHRITTE.find((s) => s.id === id)!;

/** Anteil 0..1 innerhalb eines Schritts */
export function schrittAnteil(p: number, id: (typeof SCHRITTE)[number]["id"]): number {
  const s = schritt(id);
  return Math.min(1, Math.max(0, (p - s.von) / (s.bis - s.von)));
}

const glatt = (t: number) => t * t * (3 - 2 * t);
const rampe = (s: number, a: number, b: number) => glatt(Math.min(1, Math.max(0, (s - a) / (b - a))));

export interface LinienZustand {
  /** x der Prüflinie in px */
  scanX: number;
  /** Deckkraft der Prüflinie 0..1 */
  scanAlpha: number;
  /** Achsen (Grundlinie, Ticks) */
  achsenAlpha: number;
  /** Umriss der Hohlräume (2025-03, 2025-10) */
  hohlAlpha: number;
  /** Landesgrenzen */
  grenzenAlpha: number;
  /** Nulllinie der Tabelle */
  tabellenAchseAlpha: number;
}

export function linienZustand(p: number, von: number, bis: number): LinienZustand {
  const s2 = schrittAnteil(p, "pruefen");
  const s3 = schrittAnteil(p, "zaehlen");
  const s4 = schrittAnteil(p, "belegen");
  const z = ZEITPLAN;
  const scanT = Math.min(1, Math.max(0, (s2 - z.scanVon) / (z.scanBis - z.scanVon)));
  const sichtbar = p > SCHRITTE[1].von && s2 < z.scanBis + 0.06;
  const scanAlpha = sichtbar ? rampe(s2, 0, z.scanVon) * (1 - rampe(s2, z.scanBis, z.scanBis + 0.05)) : 0;
  return {
    scanX: von + (bis - von) * scanT,
    scanAlpha,
    achsenAlpha: 1 - rampe(s3, z.folgeVon + 0.1, z.folgeVon + z.folgeStaffel + z.flug),
    hohlAlpha: 1 - rampe(s3, 0, z.ringeAusBis),
    grenzenAlpha: rampe(s3, 0.5, 0.82) * (1 - rampe(s4, 0, 0.3)),
    tabellenAchseAlpha: rampe(s4, 0.45, 0.75),
  };
}
