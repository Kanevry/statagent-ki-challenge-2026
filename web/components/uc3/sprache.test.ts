import { describe, expect, it } from "vitest";
import { alltag, alltagOder } from "./sprache";

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
});
