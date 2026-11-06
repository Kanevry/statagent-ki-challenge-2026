import { describe, expect, it } from "vitest";
import { antwortTabelle, ersterSatz, istSummenzeile, kopfSagtVerstanden, kopfSatz, rueckfrageVorschlaege, verstandenSatz } from "./antwort-ansicht";

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

  // Fehler, den das fängt: „Juli 2026 nach Regelsatz v2“ zeigte 407.604 und nur „Verstanden: Juli 2026“.
  it("nennt den Regelsatz, wenn die Antwort nach einem anderen zählt", () => {
    const antwort = {
      uc: "uc3" as const,
      text: "Nach Regelsatz v2: Im Juli 2026 gab es 407.604 Beschäftigungsverhältnisse. Die Zahl ist vorläufig.",
      belege: [{ ...beleg, monat: "2026-07" }],
      zahlen: [{ bezeichnung: "Beschäftigungsverhältnisse", wert: 407604, einheit: "Anzahl", beleg: 0 }],
    };
    expect(verstandenSatz(antwort)).toContain("Regelsatz v2");
    expect(verstandenSatz({ ...antwort, text: "Am 31. Juli 2026 gab es 399.027 Beschäftigungsverhältnisse." })).not.toContain("Regelsatz");
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

  // Fehler, den das fängt: Kopf „…, Branche: alle, Beschäftigungskategorie: alle.“ und darunter noch einmal
  // „Verstanden: Oktober 2025“ (Live-Prüfung UI-Regie 05.11. 20:00).
  it("kürzt den Kopfsatz und sagt „Verstanden“ nur einmal", () => {
    const text =
      "Verstanden: Oktober 2025, je Bundesland, je Geschlecht, Branche: alle, Beschäftigungskategorie: alle. Wien 47.922.";
    const kopf = kopfSatz(text);
    expect(kopf).toBe("Verstanden: Oktober 2025, je Bundesland, je Geschlecht.");
    expect(kopfSagtVerstanden(kopf)).toBe(true);
    expect(kopfSatz("Verstanden: März 2025, Branche: Bau.")).toBe("Verstanden: März 2025, Branche: Bau.");
    expect(kopfSagtVerstanden(kopfSatz("Im März 2025 gab es 7.498 Beschäftigungsverhältnisse."))).toBe(false);
  });

  // Fehler, den das fängt: Die Summe sieht aus wie eine Zeile mehr, oder Allentsteig wird fett.
  it("erkennt die Summenzeile", () => {
    expect(istSummenzeile("Alle Bundesländer")).toBe(true);
    expect(istSummenzeile("alle Wirtschaftsbereiche (Summe der Zeilen)")).toBe(true);
    expect(istSummenzeile("Wien")).toBe(false);
    expect(istSummenzeile("Allentsteig")).toBe(false);
  });

  it("liest die Vorschläge einer Rückfrage", () => {
    const text = "Meinen Sie „Beschäftigte Dezember 2025“, oder „Zeitreihe 01/2025 bis 12/2025“?";
    expect(rueckfrageVorschlaege(text)).toEqual(["Beschäftigte Dezember 2025", "Zeitreihe 01/2025 bis 12/2025"]);
  });
});
