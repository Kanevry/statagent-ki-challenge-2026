import { GLOSSAR } from "@kic/ui/bausteine";
import { describe, expect, it } from "vitest";
import * as inhalt from "./inhalt";
import { BEFUNDE } from "../daten/fakten";
import { BEGRIFFE, monateLesbar } from "./inhalt";

/** Alle sichtbaren Texte der Landingpage als eine Liste von Strings (Funktionen mit Beispielwerten). */
function alleTexte(wert: unknown): string[] {
  if (typeof wert === "string") return [wert];
  if (typeof wert === "function") return alleTexte((wert as (...a: number[]) => unknown)(3, 7));
  if (Array.isArray(wert)) return wert.flatMap(alleTexte);
  if (wert && typeof wert === "object") return Object.values(wert).flatMap(alleTexte);
  return [];
}

const SICHTBAR = alleTexte({
  SEITE: inhalt.SEITE,
  NAVIGATION: inhalt.NAVIGATION,
  HERO: inhalt.HERO,
  SCHRITT_TEXTE: inhalt.SCHRITT_TEXTE,
  BELEG: { ...inhalt.BELEG, sql: "" },
  SZENE_TEXTE: inhalt.SZENE_TEXTE,
  ANSATZ: inhalt.ANSATZ,
  DATENFEHLER: inhalt.DATENFEHLER,
  USE_CASES: inhalt.USE_CASES,
  TEAM: inhalt.TEAM,
  // Tabelle der Auffälligkeiten (Beispieldaten): nur die sichtbaren Felder, Monate wie in Datenfehler.tsx
  BEFUNDE: BEFUNDE.map((b) => [
    b.befund,
    monateLesbar(b.lieferung),
    monateLesbar(b.saetze),
    b.einstufungText,
    b.rueckfrage ?? "",
  ]),
});

describe("Wortliste docs/sprache.md", () => {
  it("Glossar-Texte sind wortgleich mit dem gemeinsamen Glossar", () => {
    for (const [wort, erklaerung] of Object.entries(GLOSSAR)) {
      if (wort in BEGRIFFE) expect(BEGRIFFE[wort as keyof typeof BEGRIFFE], wort).toBe(erklaerung);
    }
  });

  it.each([
    ["Verhältnis ohne „Beschäftigungs“", /(?<!Beschäftigungs)[Vv]erhältnis/],
    ["Zelle", /Zelle/],
    ["Satz im Sinn von Datensatz", /\bSätze\b|Datensatz/],
    ["Befund", /Befund/],
    ["Datenabzug", /abzug/i],
    ["Golden Set", /Golden Set/i],
    ["Monat als JJJJ-MM", /\b\d{4}-\d{2}\b/],
    ["Gedankenstrich", /[—–]/],
  ])("kein %s in sichtbarem Text", (_name, muster) => {
    expect(SICHTBAR.filter((t) => muster.test(t))).toEqual([]);
  });

  it("schreibt Monate in Anzeigetexten als MM/JJJJ", () => {
    expect(monateLesbar("78.949, davon 78.733 in 2025-11 wieder da")).toBe("78.949, davon 78.733 in 11/2025 wieder da");
    expect(monateLesbar("2024-12 → 2025-01")).toBe("12/2024 → 01/2025");
    expect(monateLesbar("alle 24")).toBe("alle 24");
  });
});
