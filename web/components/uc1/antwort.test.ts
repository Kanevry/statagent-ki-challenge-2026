import { describe, expect, it } from "vitest";
import { jaNeinFrage, quelleAnzeige } from "./antwort";

describe("quelleAnzeige", () => {
  // Fängt: ein roher Dateipfad des Kerns („Anträge und Formulare/….pdf“) auf der Seite.
  it("macht aus einem Pfad den Dateinamen ohne Endung und lange Ziffern, Seite bleibt", () => {
    expect(quelleAnzeige("Anträge und Formulare/PAL080_2026.pdf, S. 5")).toBe("PAL080, S. 5");
    expect(quelleAnzeige("a/b/Serviceratgeber.pdf")).toBe("Serviceratgeber");
    expect(quelleAnzeige("BPGG § 22 Abs. 1 Z 1")).toBe("BPGG § 22 Abs. 1 Z 1");
  });
});

describe("jaNeinFrage", () => {
  // Fängt: „Ja / Nein“ als Antwort auf eine offene Frage wie „Von wem bekommt die Person ihre Pension?“.
  it("nur bei Fragen, die mit dem Verb beginnen", () => {
    expect(jaNeinFrage("Von wem bekommt die Person ihre Pension? Zum Beispiel PVA.")).toBe(false);
    expect(jaNeinFrage("Wer braucht die Hilfe: Sie selbst oder jemand aus Ihrer Familie?")).toBe(false);
    expect(jaNeinFrage("In welchem Bundesland wohnt die Person?")).toBe(false);
    expect(jaNeinFrage("Bekommt Ihre Mutter eine Pension?")).toBe(true);
  });
});
