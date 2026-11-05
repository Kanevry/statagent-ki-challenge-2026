import { describe, expect, it } from "vitest";
import { laufPfad, regelsatzAus, uc3Navigation, UC3_NAVIGATION } from "./navigation";

describe("Regelsatz im Pfad", () => {
  it("v3 aus einer Live-Änderung bleibt v3, sonst zeigte der Link still die Zahlen von v1", () => {
    expect(regelsatzAus("v3")).toBe("v3");
    expect(laufPfad("2025-10", regelsatzAus("v3"))).toBe("/uc3/laeufe/2025-10?regelsatz=v3");
  });

  it("alles andere ist v1, auch ein Wert, der in eine Abfrage geraten könnte", () => {
    for (const wert of [undefined, "", "v0", "x", "v1;drop", ["v2"]]) expect(regelsatzAus(wert)).toBe("v1");
    expect(laufPfad("2025-10", "v1")).toBe("/uc3/laeufe/2025-10");
  });
});

describe("uc3Navigation", () => {
  it("der Auftrag erscheint nur in der Vorführ-Instanz", () => {
    expect(uc3Navigation(false)).toBe(UC3_NAVIGATION);
    expect(uc3Navigation(true).map((p) => p.href)).toContain("/uc3/auftrag");
    expect(UC3_NAVIGATION.map((p) => p.href)).not.toContain("/uc3/auftrag");
  });
});
