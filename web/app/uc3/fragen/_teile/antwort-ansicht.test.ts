import { describe, expect, it } from "vitest";
import { antwortTabelle, ersterSatz, rueckfrageVorschlaege, verstandenSatz } from "./antwort-ansicht";

const beleg = { uc: "uc3" as const, quelle: "stat.stat_beschaeftigte", lieferung: "2025-03", monat: "2025-03" };

describe("Antwort-Ansicht (UI-Regie v1)", () => {
  // Fehler, den das fängt: „Verstanden“ fehlt oder zeigt „2025-03“ statt des ausgeschriebenen Monats.
  it("sagt, was das Programm verstanden hat", () => {
    const antwort = {
      uc: "uc3" as const,
      text: "Am 31. März 2025 gab es 7.498 Beschäftigungsverhältnisse (Wien, Gesundheits- und Sozialwesen). Weiter.",
      belege: [beleg],
      zahlen: [{ bezeichnung: "Beschäftigungsverhältnisse (Wien, Gesundheits- und Sozialwesen)", wert: 7498, einheit: "Anzahl", beleg: 0 }],
    };
    expect(verstandenSatz(antwort)).toBe("Verstanden: Wien, Gesundheits- und Sozialwesen, März 2025");
    expect(ersterSatz(antwort.text)).toBe("Am 31. März 2025 gab es 7.498 Beschäftigungsverhältnisse (Wien, Gesundheits- und Sozialwesen).");
  });

  // Fehler, den das fängt: 20 Zahlen je Bundesland als lange Liste statt Tabelle Männer | Frauen.
  it("baut aus den Bezeichnungen eine Tabelle", () => {
    const z = (b: string, wert: number) => ({ bezeichnung: `Beschäftigungsverhältnisse, ${b}`, wert, einheit: "Anzahl", beleg: 0 });
    const t = antwortTabelle([z("Männer, Wien", 1), z("Männer, Tirol", 2), z("Frauen, Wien", 3), z("Frauen, Tirol", 4)]);
    expect(t.spalten.map((s) => s.titel)).toEqual(["Männer", "Frauen"]);
    expect(t.zeilen).toEqual([
      { titel: "Wien", werte: [1, 3] },
      { titel: "Tirol", werte: [2, 4] },
    ]);
    const f = antwortTabelle([
      { bezeichnung: "Fluktuation, ÖNACE A Land- und Forstwirtschaft, Fischerei", wert: 18.33, einheit: "Prozent", beleg: 0 },
      { bezeichnung: "Zugänge, ÖNACE A Land- und Forstwirtschaft, Fischerei", wert: 579, einheit: "Anzahl", beleg: 0 },
    ]);
    expect(f.spalten).toEqual([{ titel: "Fluktuation", einheit: "%" }, { titel: "Zugänge", einheit: null }]);
    expect(f.zeilen).toEqual([{ titel: "ÖNACE A Land- und Forstwirtschaft, Fischerei", werte: [18.33, 579] }]);
    expect(antwortTabelle([])).toEqual({ spalten: [{ titel: "Wert", einheit: null }], zeilen: [] });
  });

  it("liest die Vorschläge einer Rückfrage", () => {
    const text = "Meinen Sie „Beschäftigte Dezember 2025“, oder „Zeitreihe 01/2025 bis 12/2025“?";
    expect(rueckfrageVorschlaege(text)).toEqual(["Beschäftigte Dezember 2025", "Zeitreihe 01/2025 bis 12/2025"]);
  });
});
