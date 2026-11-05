import { describe, expect, it } from "vitest";
import { formatStand, jaNeinFrage, quelleAnzeige, telefonTeile } from "./antwort";

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

describe("formatStand und telefonTeile", () => {
  // Fängt: „01.01.2015“ oder „Januar“ statt der österreichischen Form „1. Jänner 2015“.
  it("schreibt das Datum mit österreichischem Monatsnamen", () => {
    expect(formatStand("2015-01-01")).toBe("1. Jänner 2015");
    expect(formatStand("2026-11-05")).toBe("5. November 2026");
    expect(formatStand("unbekannt")).toBe("unbekannt");
  });

  // Fängt: Notrufnummern ohne Link, doppelte Links, und Ziffern in Paragrafen oder Beträgen („§ 1450a“, „1.144“).
  it("macht 1450 und 144 zu tel-Teilen, sonst nichts", () => {
    expect(telefonTeile("Rufen Sie 1450 an, im Notfall 144.")).toEqual([
      { text: "Rufen Sie " },
      { text: "1450", tel: "1450" },
      { text: " an, im Notfall " },
      { text: "144", tel: "144" },
      { text: "." },
    ]);
    expect(telefonTeile("Betrag 1.144 Euro, Zeile 14450").every((t) => !t.tel)).toBe(true);
  });
});
