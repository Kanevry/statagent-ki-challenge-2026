import { ucs } from "../src/ucs";

// Vertrag H: genau UC3 ist bewertet, Route passt zur ID, kein Status-Feld mehr (Lead-Entscheid 58).
// Fängt einen Eintrag ab, der sich versehentlich als „bewertet“ markiert, die Route verbiegt oder den
// entfallenen Status-Filter wieder einführt, den UC-Lanes dann pflegen müssten.
describe("UC-Registry", () => {
  it("hat drei UCs mit passender Route und genau einem bewerteten", () => {
    expect(ucs.map((uc) => uc.id).sort()).toEqual(["uc1", "uc2", "uc3"]);
    for (const uc of ucs) expect(uc.route).toBe(`/${uc.id}`);
    expect(ucs.filter((uc) => uc.bewertet).map((uc) => uc.id)).toEqual(["uc3"]);
  });

  it("führt nur die Felder des Vertrags, ohne status", () => {
    for (const uc of ucs) expect(Object.keys(uc).sort()).toEqual(["bewertet", "id", "kurz", "name", "route"]);
  });
});
