import { describe, expect, it } from "vitest";
import { regelsatzSatz } from "./regelsatz-satz";

describe("Satz neben dem Regelsatz-Schalter", () => {
  // Fehler, den das fängt: Die Jury erwartet 407.604, sieht 399.027 und erfährt nicht, warum.
  it("sagt, was jeder zählt, und nennt die andere Zahl", () => {
    expect(regelsatzSatz("v1", 407604)).toContain("Regelsatz v2 zählt das ganze Monat: 407.604.");
    expect(regelsatzSatz("v2", 399027)).toContain("Regelsatz v1 zählt am Monatsletzten: 399.027.");
    expect(regelsatzSatz("v3", 399027)).toBe("Das ist Regelsatz v3, mit einer freigegebenen Änderung. Regelsatz v1 zählt am Monatsletzten: 399.027.");
  });

  it("erfindet keine Zahl, wenn der andere Regelsatz den Monat nicht gerechnet hat", () => {
    expect(regelsatzSatz("v1", null)).toBe("Das ist Regelsatz v1, gezählt am Monatsletzten. Regelsatz v2 zählt das ganze Monat.");
  });
});
