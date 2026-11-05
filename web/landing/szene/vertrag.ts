/**
 * Vertrag zwischen Seite (web/landing/sektionen), Szene (web/landing/szene) und Kartendaten
 * (web/landing/karte, web/public/landing). Von der Koordination festgelegt, nur gemeinsam ändern.
 */

/** Varianten der Szene. Mobil: weniger Partikel, DPR höchstens 1,5, kürzere Sticky-Strecke. */
export type SzeneVariante = "desktop" | "mobil";

/** Die vier Schritte der Scroll-Erzählung. `von`/`bis` sind Anteile des Gesamtfortschritts 0..1. */
export const SCHRITTE = [
  { id: "lieferungen", von: 0, bis: 0.24 },
  { id: "pruefen", von: 0.24, bis: 0.5 },
  { id: "zaehlen", von: 0.5, bis: 0.76 },
  { id: "belegen", von: 0.76, bis: 1 },
] as const;

export type SchrittId = (typeof SCHRITTE)[number]["id"];

/** Höhe der Sticky-Strecke in Viewport-Höhen (inkl. der ersten Bildschirmhöhe). */
export const STRECKE_VH: Record<SzeneVariante, number> = { desktop: 460, mobil: 360 };

/** Partikelzahl je Variante. Jede Karte-Datei liefert mindestens PARTIKEL.desktop Punkte. */
export const PARTIKEL: Record<SzeneVariante, number> = { desktop: 48_000, mobil: 14_000 };

/** Fortschritts-Speicher ohne React-State, damit Scrollen keine Re-Renders auslöst. */
export interface FortschrittSpeicher {
  /** 0..1 über die gesamte Sticky-Strecke */
  wert(): number;
  setzen(p: number): void;
  /** Rückgabe: Abmelden */
  abonnieren(f: (p: number) => void): () => void;
}

export function erzeugeFortschritt(start = 0): FortschrittSpeicher {
  let p = start;
  const hoerer = new Set<(p: number) => void>();
  return {
    wert: () => p,
    setzen(neu) {
      const k = Math.min(1, Math.max(0, neu));
      if (k === p) return;
      p = k;
      for (const h of hoerer) h(p);
    },
    abonnieren(f) {
      hoerer.add(f);
      return () => hoerer.delete(f);
    },
  };
}

/** Props der Client-Komponente `SzeneCanvas` (web/landing/szene/SzeneCanvas.tsx). */
export interface SzeneCanvasProps {
  fortschritt: FortschrittSpeicher;
  variante: SzeneVariante;
  /** prefers-reduced-motion: ein ruhiges Standbild, kein Scroll-Scrubbing, keine Leerlauf-Animation */
  reduziert: boolean;
  /** CSS-Klasse für das Canvas-Element (Seite steuert Lage und Größe) */
  className?: string;
}

/**
 * Kartendaten (erzeugt von web/landing/werkzeug, geladen über web/landing/karte/laden.ts).
 *
 * Datei `web/public/landing/oesterreich-punkte.bin`, little-endian:
 *   Byte 0..3      Uint32  N (Anzahl Punkte)
 *   danach         N × Uint16 x   (0..65535 → 0..1, links → rechts)
 *   danach         N × Uint16 y   (0..65535 → 0..1, oben → unten)
 *   danach         N × Uint8  bl  (Bundesland-Code 1..9 wie fakten.ts)
 * Reihenfolge: jedes Präfix der Länge n ist eine geschichtete Stichprobe, d. h. der Anteil je
 * Bundesland entspricht (±1 Punkt) dem Anteil an BUNDESLAENDER_2024_08 ohne Code 0.
 * Punkte liegen gleichmäßig zufällig (fester Seed) innerhalb der Landesgrenze.
 *
 * Datei `web/public/landing/oesterreich-meta.json`: KartenMeta.
 */
export interface KartenMeta {
  quelle: string;
  lizenz: string;
  /** Breite / Höhe des normierten Rechtecks (Projektion: äquirektangulär mit cos(47,6°)) */
  seitenverhaeltnis: number;
  n: number;
  laender: { code: number; name: string; label: [number, number]; anteil: number }[];
  /** Landesgrenzen als Polylinien, normiert 0..1, je Linie flach [x0, y0, x1, y1, ...] */
  grenzen: number[][];
}

export interface KartenDaten {
  n: number;
  /** 0..1 */
  x: Float32Array;
  /** 0..1, oben → unten */
  y: Float32Array;
  bl: Uint8Array;
  meta: KartenMeta;
}

export const KARTE_URL = {
  punkte: "/landing/oesterreich-punkte.bin",
  meta: "/landing/oesterreich-meta.json",
} as const;
