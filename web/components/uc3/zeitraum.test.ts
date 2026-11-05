import { describe, expect, it } from "vitest";
import { sqlBestand, sqlMonatszeile } from "./beleg";
import { sqlAbschnittBestand } from "./klassifikation";
import { bestandSatz, sqlBestandMitVormonat, sqlKennzahlen, sqlRegionen } from "./lauf-detail";
import type { Lauf } from "./typen";
import { bestandFilter, bestandJeMonat, imZeitraum, imZeitraumText, zeitraumArtAus } from "./zeitraum";

const lauf = (zeitraumArt: "Stichtag" | "Monat", regelsatz: string, gezaehlt: number) =>
  ({ id: 1, quelleId: 1, lieferung: "2026-07", regelsatz, regelstand: "abc", zeitraumArt, gezaehlt }) as Lauf;
const v1 = lauf("Stichtag", "v1", 399027);
const v2 = lauf("Monat", "v2", 407604);

describe("Zeitraumart je Regelsatz", () => {
  it("fällt ohne Angabe auf den Stichtag zurück", () => {
    expect(zeitraumArtAus("Monat")).toBe("Monat");
    expect(zeitraumArtAus("Stichtag")).toBe("Stichtag");
    expect(zeitraumArtAus(null)).toBe("Stichtag");
    expect(zeitraumArtAus(undefined)).toBe("Stichtag");
  });

  it("nennt je Regelsatz den richtigen Zeitraum", () => {
    expect(bestandSatz(v1, null)).toBe("Am 31.07.2026 bestanden 399.027 Beschäftigungsverhältnisse.");
    expect(bestandSatz(v2, null)).toBe("Im Juli 2026 bestanden 407.604 Beschäftigungsverhältnisse.");
    expect(imZeitraum("Stichtag")).toBe("am Stichtag");
    expect(imZeitraum("Monat")).toBe("im Monat");
    expect(bestandJeMonat("Stichtag")).toBe("Beschäftigungsverhältnisse am Stichtag je Monat");
    expect(bestandJeMonat("Monat")).toBe("Beschäftigungsverhältnisse je Monat");
  });

  // Fängt: fester Filter auf 'Stichtag'; für v2 liefert der Beleg dann NULL statt 407.604.
  it.each([
    ["sqlBestand", sqlBestand],
    ["sqlMonatszeile", sqlMonatszeile],
    ["sqlRegionen", sqlRegionen],
    ["sqlBestandMitVormonat", (l: Lauf) => sqlBestandMitVormonat(l, null)],
    ["sqlAbschnittBestand", (l: Lauf) => sqlAbschnittBestand(l, l)],
  ])("%s filtert auf die Zeitraumart des Laufs", (_name, abfrage) => {
    expect(abfrage(v1)).toContain("zeitraum_art = 'Stichtag'");
    expect(abfrage(v1)).not.toContain("'Monat'");
    expect(abfrage(v2)).toContain("zeitraum_art = 'Monat'");
    expect(abfrage(v2)).not.toContain("'Stichtag'");
  });

  it("benennt die Spalte im Beleg passend", () => {
    expect(sqlKennzahlen(v1)).toContain("bestand_am_stichtag");
    expect(sqlKennzahlen(v2)).toContain("bestand_im_monat");
  });

  it("baut den Filter mit und ohne Tabellenalias", () => {
    expect(bestandFilter("Monat")).toBe("zeitraum_art = 'Monat' AND variable = 'Beschaeftigungsverhaeltnisse'");
    expect(bestandFilter("Monat", "s.")).toBe("s.zeitraum_art = 'Monat' AND s.variable = 'Beschaeftigungsverhaeltnisse'");
  });

  it("schreibt gespeicherte Befundtexte nur beim Zählen über das Monat um, das Alter bleibt am Stichtag", () => {
    const text = "9 Verhältnisse am Stichtag, Alter in vollendeten Jahren am Stichtag";
    expect(imZeitraumText(text, "Stichtag")).toBe(text);
    expect(imZeitraumText(text, "Monat")).toBe("9 Verhältnisse im Berichtsmonat, Alter in vollendeten Jahren am Stichtag");
  });
});
