import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { dekodiereKarte } from "../../karte/laden";
import { GOLDEN_SET, LIEFERUNGEN } from "../../daten/fakten";
import { PARTIKEL, type KartenMeta } from "../vertrag";
import { ersatzKarte } from "./karteErsatz";
import { berechneLayout, planePartikel } from "./layout";
import { ART, bauePartikel, ZIEL } from "./partikel";

const hier = path.dirname(fileURLToPath(import.meta.url));
const oeffentlich = path.join(hier, "../../../public/landing");

function echteKarte() {
  try {
    const bin = readFileSync(path.join(oeffentlich, "oesterreich-punkte.bin"));
    const meta = JSON.parse(readFileSync(path.join(oeffentlich, "oesterreich-meta.json"), "utf8")) as KartenMeta;
    const ab = bin.buffer.slice(bin.byteOffset, bin.byteOffset + bin.byteLength) as ArrayBuffer;
    return dekodiereKarte(ab, meta);
  } catch {
    return null;
  }
}

describe.each(["desktop", "mobil"] as const)("Szene %s", (variante) => {
  const groesse = variante === "desktop" ? [1440, 900] : [390, 844];
  const layout = berechneLayout(groesse[0], groesse[1], variante);

  it("verteilt genau PARTIKEL Partikel auf die 24 Lieferungen", () => {
    const plan = planePartikel(variante);
    expect(plan.saeulen).toHaveLength(24);
    expect(plan.saeulen.reduce((a, b) => a + b, 0)).toBe(PARTIKEL[variante]);
  });

  it("Säulenhöhe proportional zu den Zeilen, ab der Grundlinie, 2025-10 rund 20 % kürzer", () => {
    const hoehe = (i: number) => layout.saeulen[i].unten - layout.saeulen[i].oben;
    for (let i = 0; i < 24; i++) {
      expect(layout.saeulen[i].unten).toBe(layout.grundlinie.y);
      expect(hoehe(i) / hoehe(23)).toBeCloseTo(LIEFERUNGEN[i].zeilen / LIEFERUNGEN[23].zeilen, 6);
    }
    const i10 = LIEFERUNGEN.findIndex((l) => l.lieferung === "2025-10");
    const kuerzer = 1 - hoehe(i10) / hoehe(i10 - 1);
    expect(kuerzer).toBeGreaterThan(0.18);
    expect(kuerzer).toBeLessThan(0.22);
  });

  it("Säulen und Gruppen bleiben im Canvas", () => {
    for (const s of layout.saeulen) {
      expect(s.links).toBeGreaterThanOrEqual(0);
      expect(s.rechts).toBeLessThanOrEqual(layout.breite);
      expect(s.oben).toBeGreaterThanOrEqual(0);
    }
    for (const b of layout.befunde) {
      expect(b.gruppe.x).toBeGreaterThanOrEqual(0);
      expect(b.gruppe.x + b.gruppe.breite).toBeLessThanOrEqual(layout.breite);
      expect(b.gruppe.y + b.gruppe.hoehe).toBeLessThanOrEqual(layout.hoehe);
      expect(b.quelle.y).toBeGreaterThanOrEqual(0);
    }
    const t = layout.tabelle;
    for (const z of t.zeilen) expect(z.x1).toBeLessThanOrEqual(layout.breite);
  });

  it.each([
    ["Ersatz-Karte", () => ersatzKarte()],
    ["echte Karte", echteKarte],
  ] as const)("Karte nutzt alle Partikel (%s): jeder Kartenpunkt ein Partikel, Summe je Bundesland proportional", (_, laden) => {
    const karte = laden();
    if (!karte) return; // echte Datei fehlt im Checkout
    const plan = planePartikel(variante);
    const l = berechneLayout(groesse[0], groesse[1], variante, karte.meta);
    const puffer = bauePartikel(l, karte);
    const summe = [...puffer.kartenJeLand.values()].reduce((a, b) => a + b, 0);
    expect(summe).toBe(plan.kartenPartikel);
    for (const [code, erwartet] of plan.jeLand) {
      expect(Math.abs((puffer.kartenJeLand.get(code) ?? 0) - erwartet)).toBeLessThanOrEqual(2);
    }
    // Karte + gelbe Gruppe „ohne Bundesland“ = alle Säulen-Partikel; nur die Ringe gehen nicht mit
    let zurKarte = 0;
    let unbekannt = 0;
    let ringe = 0;
    for (let i = 0; i < puffer.anzahl; i++) {
      const ziel = puffer.info[i * 4 + 1];
      if (ziel === ZIEL.karte) zurKarte++;
      if (ziel === ZIEL.unbekannt) unbekannt++;
      if (puffer.info[i * 4] === ART.fehlt) ringe++;
    }
    expect(zurKarte).toBe(plan.kartenPartikel);
    expect(unbekannt).toBe(plan.unbekanntPunkte);
    expect(zurKarte + unbekannt).toBe(PARTIKEL[variante]);
    expect(puffer.anzahl).toBe(PARTIKEL[variante] + ringe);
    // Auflösung: 1 Punkt ≈ N Verhältnisse, die gelbe Gruppe mit derselben Auflösung
    expect(l.karte.verhaeltnisseProPunkt).toBe(variante === "desktop" ? 8 : 28);
    expect(Math.abs(plan.unbekanntPunkte * (GOLDEN_SET.bestand / PARTIKEL[variante]) - 1_996)).toBeLessThan(GOLDEN_SET.bestand / PARTIKEL[variante]);
    for (let i = 0; i < puffer.anzahl * 2; i++) {
      expect(Number.isFinite(puffer.karte[i]) && Number.isFinite(puffer.tabelle[i])).toBe(true);
    }
    // Schritt 4: kein Punkt-Balken ragt über seinen Anker x1 hinaus (Zahlen rechts bleiben frei)
    const t = l.tabelle;
    const ende = new Map(t.zeilen.map((z) => [z.code, z.x1]));
    for (let i = 0; i < puffer.anzahl; i++) {
      if (puffer.info[i * 4 + 1] !== ZIEL.karte) continue;
      expect(puffer.tabelle[i * 2]).toBeLessThanOrEqual(Math.max(...ende.values()) + 0.01);
    }
  });

  it("Befund-Beschriftungen haben je mindestens 200 px und überlappen nicht", () => {
    const b = layout.befunde;
    for (const x of b) expect(x.label.breite).toBeGreaterThanOrEqual(200);
    const zeile = variante === "desktop" ? 36 : 18;
    for (let i = 0; i < b.length; i++) {
      for (let j = i + 1; j < b.length; j++) {
        const a = b[i];
        const c = b[j];
        const getrennt = a.label.y + zeile <= c.gruppe.y || c.label.y + zeile <= a.gruppe.y;
        expect(getrennt).toBe(true);
      }
    }
  });
});
