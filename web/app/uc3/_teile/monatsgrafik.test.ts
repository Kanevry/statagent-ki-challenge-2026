import { describe, expect, it } from "vitest";
import { namensLage } from "./monatsgrafik";

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
