/**
 * Ersatz-Karte, solange `oesterreich-punkte.bin` fehlt oder nicht lädt: je Bundesland ein grobes
 * Rechteck in geografischer Lage (West → Ost), Punkte gleichverteilt mit festem Seed, Reihenfolge
 * geschichtet wie die echte Datei (jedes Präfix trägt die Anteile aus BUNDESLAENDER_2024_08).
 * Gleiches Format wie KartenDaten, damit der Wechsel nur den Loader-Aufruf betrifft.
 */
import { BUNDESLAENDER_2024_08 } from "../../daten/fakten";
import { PARTIKEL, type KartenDaten, type KartenMeta } from "../vertrag";
import { ERSATZ_LABEL, KARTE_SEITENVERHAELTNIS_ERSATZ } from "./layout";
import { zufallsquelle } from "./zufall";

/** [x0, y0, x1, y1] normiert, grob nach Lage der Länder */
const RECHTECKE: Record<number, [number, number, number, number]> = {
  8: [0.0, 0.42, 0.07, 0.78],
  7: [0.07, 0.42, 0.33, 0.8],
  5: [0.33, 0.32, 0.48, 0.78],
  2: [0.4, 0.8, 0.66, 1.0],
  4: [0.48, 0.02, 0.66, 0.48],
  6: [0.55, 0.5, 0.85, 0.8],
  3: [0.66, 0.0, 0.93, 0.5],
  9: [0.85, 0.22, 0.9, 0.31],
  1: [0.88, 0.5, 0.97, 0.95],
};

export function ersatzKarte(n = PARTIKEL.desktop): KartenDaten {
  const laender = BUNDESLAENDER_2024_08.filter((l) => l.code !== 0);
  const summe = laender.reduce((a, l) => a + l.anzahl, 0);
  const anteil = laender.map((l) => l.anzahl / summe);
  const zugeteilt = laender.map(() => 0);
  const zufall = zufallsquelle(0x5eed_a7);
  const x = new Float32Array(n);
  const y = new Float32Array(n);
  const bl = new Uint8Array(n);
  const wien = RECHTECKE[9];
  for (let i = 0; i < n; i++) {
    // Land mit dem größten Rückstand gegenüber seinem Soll-Anteil
    let best = 0;
    let bestRueck = -Infinity;
    for (let k = 0; k < laender.length; k++) {
      const rueck = anteil[k] * (i + 1) - zugeteilt[k];
      if (rueck > bestRueck) {
        bestRueck = rueck;
        best = k;
      }
    }
    zugeteilt[best]++;
    const code = laender[best].code;
    const [x0, y0, x1, y1] = RECHTECKE[code];
    let px = 0;
    let py = 0;
    for (let versuch = 0; versuch < 20; versuch++) {
      px = x0 + zufall() * (x1 - x0);
      py = y0 + zufall() * (y1 - y0);
      // Niederösterreich umschließt Wien
      const inWien = px >= wien[0] && px <= wien[2] && py >= wien[1] && py <= wien[3];
      if (code === 9 || !inWien) break;
    }
    x[i] = px;
    y[i] = py;
    bl[i] = code;
  }
  const grenzen = Object.values(RECHTECKE).map(([x0, y0, x1, y1]) => [x0, y0, x1, y0, x1, y1, x0, y1, x0, y0]);
  const meta: KartenMeta = {
    quelle: "Ersatz-Raster (keine Geodaten)",
    lizenz: "keine",
    seitenverhaeltnis: KARTE_SEITENVERHAELTNIS_ERSATZ,
    n,
    laender: laender.map((l, k) => ({
      code: l.code,
      name: l.name,
      label: ERSATZ_LABEL[l.code] ?? [0.5, 0.5],
      anteil: anteil[k],
    })),
    grenzen,
  };
  return { n, x, y, bl, meta };
}
