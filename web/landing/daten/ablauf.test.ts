import { describe, expect, it } from "vitest";
import { ABLAUF } from "./ablauf";

const alles = [
  ABLAUF.titel,
  ABLAUF.satz,
  ABLAUF.zahlen,
  ...ABLAUF.zeitleiste.flatMap((p) => [p.zeit, p.satz]),
  ...ABLAUF.abschnitte.flatMap((a) => [a.titel, ...a.saetze]),
];

describe("Seite Ablauf", () => {
  it("hat die vier Abschnitte in der vereinbarten Reihenfolge", () => {
    expect(ABLAUF.ueberschriften.zeitleiste).toBeTruthy();
    expect(ABLAUF.abschnitte.map((a) => a.id)).toEqual(["arbeit", "schwierig", "offen"]);
  });

  it("bleibt kurz: höchstens acht Zeilen Zeitleiste, höchstens drei Sätze je Abschnitt", () => {
    expect(ABLAUF.zeitleiste.length).toBeGreaterThan(0);
    expect(ABLAUF.zeitleiste.length).toBeLessThanOrEqual(8);
    for (const a of ABLAUF.abschnitte) {
      expect(a.saetze.length, a.id).toBeGreaterThan(0);
      expect(a.saetze.length, a.id).toBeLessThanOrEqual(3);
    }
  });

  it("steht zeitlich in Reihenfolge und zeigt nichts nach dem Stand der Daten", () => {
    const zeiten = ABLAUF.zeitleiste.map((p) => Date.parse(p.iso));
    expect(zeiten.every((z) => !Number.isNaN(z))).toBe(true);
    expect(zeiten).toEqual([...zeiten].sort((a, b) => a - b));
    expect(Math.max(...zeiten)).toBeLessThanOrEqual(Date.parse(ABLAUF.standIso));
  });

  it.each([
    // „CI-Server“ und „Zweitrechner“ sind die erlaubten Namen auf der Seite.
    ["Rechnername", /\b(m4|m5|win-wsl|sven|gitlab-box|runner-manager)\b|\bci-server\b/],
    ["MR- oder Issue-Nummer", /(?:^|\s)[!#]\d+/],
    ["Sitzungsname", /\b(lead-session|b-[a-z0-9]+-[0-9a-f]{2}|ui-regie|e5-szenen)\b/i],
    ["Gedankenstrich", /[—–]/],
    ["Verhältnis ohne „Beschäftigungs“", /(?<!Beschäftigungs)[Vv]erhältnis/],
    ["Regelsatz-Kürzel", /\bv[12]\b/],
    ["nicht Gemessenes", /nicht gemessen/i],
  ])("kein %s auf der öffentlichen Seite", (_name, muster) => {
    expect(alles.filter((t) => muster.test(t))).toEqual([]);
  });
});
