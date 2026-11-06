import { describe, expect, it } from "vitest";
import { achsenBeginn, achsenHinweis, namensLage } from "./monatsgrafik";

describe("achsenHinweis", () => {
  it("nennt den berechneten Achsenbeginn und sagt, dass er nicht 0 ist", () => {
    const satz = achsenHinweis(achsenBeginn([386_996, 388_650, 390_900]));
    expect(satz).toContain("Die Achse beginnt bei 385");
    expect(satz).toContain("nicht bei 0");
  });
  it("behauptet nichts Falsches, wenn die Achse doch bei 0 beginnt", () => {
    expect(achsenHinweis(0)).toBe("Die Achse beginnt bei 0.");
  });
});

describe("namensLage", () => {
  it("setzt den Namen über eine Spitze und unter eine Senke", () => {
    expect(namensLage(386_996, 388_650, 387_601).dy).toBeLessThan(0);
    expect(namensLage(390, 380, 395).dy).toBeGreaterThan(0);
  });
  it("weicht bei fallender Linie nach rechts oben aus, bei steigender nach links oben", () => {
    expect(namensLage(394_200, 390_900, 389_823)).toEqual({ dx: 10, dy: -8, anker: "start" });
    expect(namensLage(380, 390, 400)).toEqual({ dx: -10, dy: -8, anker: "end" });
  });
  it("kommt am Rand mit einem Nachbarn aus", () => {
    expect(namensLage(undefined, 390, 380).dy).toBeLessThan(0);
    expect(namensLage(380, 390, undefined).dy).toBeLessThan(0);
  });
});
