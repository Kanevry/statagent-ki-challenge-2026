import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { BUNDESLAENDER_2024_08 } from "../daten/fakten";
import { PARTIKEL, type KartenMeta } from "../szene/vertrag";
import { dekodiereKarte } from "./laden";

const ordner = join(__dirname, "..", "..", "public", "landing");
const roh = readFileSync(join(ordner, "oesterreich-punkte.bin"));
const buf = roh.buffer.slice(roh.byteOffset, roh.byteOffset + roh.byteLength) as ArrayBuffer;
const meta = JSON.parse(readFileSync(join(ordner, "oesterreich-meta.json"), "utf8")) as KartenMeta;
const karte = dekodiereKarte(buf, meta);

const laender = BUNDESLAENDER_2024_08.filter((b) => b.code !== 0);
const gesamt = laender.reduce((s, b) => s + b.anzahl, 0);

describe("Kartendaten Österreich", () => {
  it.each([PARTIKEL.mobil, PARTIKEL.desktop])(
    "jedes Präfix (%i Punkte) hält den Anteil je Bundesland auf ±1",
    (n) => {
      const zaehler = new Map<number, number>();
      for (let i = 0; i < n; i++) zaehler.set(karte.bl[i], (zaehler.get(karte.bl[i]) ?? 0) + 1);
      for (const b of laender) {
        const soll = (n * b.anzahl) / gesamt;
        expect(Math.abs((zaehler.get(b.code) ?? 0) - soll), b.name).toBeLessThanOrEqual(1.5);
      }
    },
  );

  it("Wien liegt als eigenes Gebiet, kein Niederösterreich-Punkt im Wiener Kern", () => {
    let wx = 0, wy = 0, wn = 0;
    for (let i = 0; i < karte.n; i++)
      if (karte.bl[i] === 9) {
        wx += karte.x[i];
        wy += karte.y[i];
        wn++;
      }
    const cx = wx / wn;
    const cy = wy / wn;
    // Radius ~3 km um den Schwerpunkt Wiens (Wien ist ~25 km breit, Österreich ~575 km)
    const r = 3 / 575;
    for (let i = 0; i < karte.n; i++) {
      if (karte.bl[i] !== 3) continue;
      const d = Math.hypot((karte.x[i] - cx) * meta.seitenverhaeltnis, karte.y[i] - cy) / meta.seitenverhaeltnis;
      expect(d).toBeGreaterThan(r);
    }
  });

  it("lehnt eine abgeschnittene Datei ab", () => {
    expect(() => dekodiereKarte(buf.slice(0, buf.byteLength - 1), meta)).toThrow(/erwartet/);
  });
});
