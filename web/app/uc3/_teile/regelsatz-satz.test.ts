import { describe, expect, it } from "vitest";
import { imStand, mitRegeln, regelsatzName, regelsatzSatz } from "@/components/uc3/regelsatz-name";

describe("Wörter für die Fassungen der Regeln", () => {
  // Fehler, den das fängt: Auf einer Seite steht wieder „v2“, das niemand ohne Vorwissen versteht.
  it("zeigt nie die Kurzform aus der Adresse", () => {
    for (const r of ["v1", "v2", "v3", "ministerium"]) {
      for (const text of [regelsatzName(r), mitRegeln(r), imStand(r), regelsatzSatz(r, 399027)]) {
        expect(text).not.toMatch(/\bv\d+\b|Regelsatz/);
      }
    }
    expect(regelsatzName("v1")).toBe("Alte Regeln");
    expect(regelsatzName("v2")).toBe("Nach den Änderungsaufträgen");
    expect(regelsatzName("v3")).toBe("Neue Fassung 3");
  });
});

describe("Satz neben dem Schalter", () => {
  // Fehler, den das fängt: 399.027 und 407.604 stehen nebeneinander, und niemand sagt, was der Unterschied ist.
  it("sagt, was hier zählt, und nennt die Zahl des anderen Stands", () => {
    expect(regelsatzSatz("v1", 407604)).toBe(
      "Sie sehen die alten Regeln: Gezählt wird am Monatsletzten. Nach den Änderungsaufträgen zählt der ganze Monat: 407.604.",
    );
    expect(regelsatzSatz("v2", 399027)).toBe(
      "Sie sehen den Stand nach den Änderungsaufträgen: Gezählt wird über den ganzen Monat. Nach den alten Regeln, am Monatsletzten, sind es 399.027.",
    );
    expect(regelsatzSatz("v3", 399027)).toBe("Sie sehen eine neue Fassung mit einer frisch freigegebenen Änderung. Nach den alten Regeln sind es 399.027.");
  });

  it("erfindet keine Zahl, wenn der andere Stand den Monat nicht gerechnet hat", () => {
    expect(regelsatzSatz("v1", null)).toBe("Sie sehen die alten Regeln: Gezählt wird am Monatsletzten. Nach den Änderungsaufträgen zählt der ganze Monat.");
    expect(regelsatzSatz("v2", null)).not.toMatch(/\d/);
  });
});
