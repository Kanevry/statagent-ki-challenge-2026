import { describe, expect, it } from "vitest";
import { gruppeAus, inGruppen } from "./einstufung-gruppen";

describe("Gruppen der Auffälligkeiten", () => {
  it("ordnet nur nach der gespeicherten Einstufung, ohne Einstufung gilt noch nicht erklärt", () => {
    expect(gruppeAus("erklaert-datenproblem")).toBe("fehler");
    expect(gruppeAus("erklaert-plausibel")).toBe("kein-fehler");
    expect(gruppeAus("nicht-erklaerbar")).toBe("offen");
    expect(gruppeAus(null)).toBe("offen");
  });

  it("feste Reihenfolge der Gruppen, Reihenfolge innerhalb bleibt, leere Gruppen fallen weg", () => {
    const gruppen = inGruppen([
      { n: 1, einstufung: "nicht-erklaerbar" },
      { n: 2, einstufung: "erklaert-datenproblem" },
      { n: 3, einstufung: "erklaert-datenproblem" },
    ]);
    expect(gruppen.map((g) => g.gruppe.art)).toEqual(["fehler", "offen"]);
    expect(gruppen[0]?.eintraege.map((e) => e.n)).toEqual([2, 3]);
  });
});
