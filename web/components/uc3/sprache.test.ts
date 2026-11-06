import { describe, expect, it } from "vitest";
import { alltag, alltagOder, detailsText } from "./sprache";

describe("alltag", () => {
  it("lässt Beschäftigungsverhältnis unverändert", () => {
    const text = "Jedes Beschäftigungsverhältnis zählt, auch Beschäftigungsverhältnisse mit Beginn am Stichtag.";
    expect(alltag(text)).toBe(text);
  });

  it("macht aus Verhältnis allein das Beschäftigungsverhältnis, mit gleicher Endung", () => {
    expect(alltag("Bei 391 Verhältnissen fehlt das Geburtsdatum.")).toBe("Bei 391 Beschäftigungsverhältnissen fehlt das Geburtsdatum.");
    expect(alltag("Ein Verhältnis zählt; 280 Verhältnisse; Zeitabschnitt des Verhältnisses.")).toBe(
      "Ein Beschäftigungsverhältnis zählt; 280 Beschäftigungsverhältnisse; Zeitabschnitt des Beschäftigungsverhältnisses.",
    );
  });

  it("lässt „im Verhältnis zu“ und kleingeschriebene Zusammensetzungen stehen", () => {
    expect(alltag("Im Verhältnis zum Vormonat ein Mischverhältnis.")).toBe("Im Verhältnis zum Vormonat ein Mischverhältnis.");
  });

  it("schreibt lieferung_JJJJ-MM und alleinstehende Monate aus", () => {
    expect(alltag("lieferung_2025-10 und alle weiteren")).toBe("Lieferung Oktober 2025 und alle weiteren");
    expect(alltag("Teil-Lieferung 2025-10: 313.154 gegen 394.200 in 2025-09.")).toBe(
      "Teil-Lieferung Oktober 2025: 313.154 gegen 394.200 in September 2025.",
    );
    expect(alltag("Berichtsmonat 2025-01 (v1) veröffentlichen")).toBe("Berichtsmonat Jänner 2025 (v1) veröffentlichen");
  });

  it("lässt Datum, Hash, Code und Literal unverändert", () => {
    const text = "Stichtag 2025-10-31, Lauf c3ecc4472025-10, Datei uc3/2025-10.csv, Wert '2025-10', Regel P04_2025-10.";
    expect(alltag(text)).toBe(text);
  });

  it("wird nie auf SQL angewendet: der Beleg bleibt der Rohtext", () => {
    // Die Seiten übergeben SQL nicht an alltag; dieser Fall hält fest, dass das nötig ist.
    const sql = "SELECT count(*) FROM roh.lieferung WHERE lieferung = 2025-10";
    expect(alltag(sql)).not.toBe(sql);
  });

  it("lässt null stehen", () => {
    expect(alltagOder(null)).toBeNull();
    expect(alltagOder("10 Verhältnisse")).toBe("10 Beschäftigungsverhältnisse");
  });

  // Fehler (Review !77, Punkt 5): „Unbekannt (UNB bzw. 0), Satz zählt“ aus der Datenbank, die Seite sagt sonst „Zeile“.
  it("macht aus Satz und Sätze Zeile und Zeilen, Regelsatz bleibt", () => {
    expect(alltag("Unbekannt (UNB bzw. 0), Satz zählt.")).toBe("Unbekannt (UNB bzw. 0), Zeile zählt.");
    expect(alltag("1.663 Sätze, Regelsatz v2")).toBe("1.663 Zeilen, Regelsatz v2");
  });

  // Fehler: „zu einem Satz verdichtet“ wurde „zu einem Zeile verdichtet“.
  it("passt den Artikel an: einem Satz wird einer Zeile", () => {
    expect(alltag("zu einem Satz verdichtet, der Satz zählt")).toBe("zu einer Zeile verdichtet, die Zeile zählt");
  });
});

describe("detailsText", () => {
  // Wörtlich aus uc3/db/100_klass_daten.sql (stat.variable, Beschreibung der Beschäftigungsverhältnisse).
  const definition =
    "Anzahl der Versicherungsverhältnisse (VVH_ID), die im Berichtszeitraum bestehen. Regelsatz v1: am Stichtag (Monatsletzter) besteht ein Zeitabschnitt mit Beginn ≤ Stichtag und Ende leer oder ≥ Stichtag; Merkmale aus diesem Abschnitt; jedes Verhältnis einmal. Die genaue Zählregel je Regelstand steht in meta.regel (typ zaehl).";

  it("schreibt die Definition aus der Datenbank in den Wörtern der App", () => {
    for (const roh of ["VVH_ID", "Regelsatz v1", "Monatsletzter", "meta.regel"]) {
      expect(definition).toContain(roh);
      expect(detailsText(definition)).not.toContain(roh);
    }
    expect(detailsText(definition)).toBe(
      "Anzahl der Beschäftigungsverhältnisse, die im Berichtszeitraum bestehen. Nach den alten Regeln gilt: Am Stichtag, dem letzten Tag des Monats, besteht ein Zeitabschnitt mit Beginn ≤ Stichtag und Ende leer oder ≥ Stichtag; Merkmale aus diesem Abschnitt; jedes Beschäftigungsverhältnis einmal. Die genaue Zählregel je Regelstand steht in den freigegebenen Regeln.",
    );
  });

  it("Monatsletzter am Satzende (frage.py, Ersatztext ohne Datenbank)", () => {
    const vorher = "Beschäftigungsverhältnisse am Stichtag (Monatsletzter).";
    expect(vorher).toContain("Monatsletzter");
    expect(detailsText(vorher)).toBe("Beschäftigungsverhältnisse am Stichtag, dem letzten Tag des Monats.");
  });

  it("Monatsletzter und stat.-Tabellen in der Fluktuation (frage.py, FLUKTUATION_DEFINITION)", () => {
    const vorher =
      "Bestand: Beschäftigungsverhältnisse am Stichtag (Monatsletzter) laut stat.stat_beschaeftigte im Regelstand des maßgeblichen Laufs. Beide Stichtage aus der Lieferung des Berichtsmonats (stat.bewegung_oenace).";
    const nachher = detailsText(vorher);
    expect(nachher).toBe(
      "Bestand: Beschäftigungsverhältnisse am Stichtag, dem letzten Tag des Monats, laut der gerechneten Statistik im Regelstand des maßgeblichen Laufs. Beide Stichtage aus der Lieferung des Berichtsmonats.",
    );
    expect(nachher).not.toMatch(/Monatsletzt|stat\./);
  });

  it("lässt Text ohne Rohwörter und alle Zahlen unverändert", () => {
    // Wörtlich aus web/components/uc3/fixtures/antwort-wien-2025-03.json.
    const text = "Am Stichtag 31.03.2025 (März 2025) gab es 91.450 Beschäftigungsverhältnisse (Wien); die Zahl ist vorläufig (Lauf 105).";
    expect(detailsText(text)).toBe(text);
  });
});
