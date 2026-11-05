import { ucs } from "../src/ucs";

// Vertrag H: genau UC3 ist bewertet, Route passt zur ID. Fängt einen UC-Eintrag ab,
// der sich beim Einhängen versehentlich als „bewertet“ markiert oder die Route verbiegt.
describe("UC-Registry", () => {
  it("hat drei UCs mit passender Route und genau einem bewerteten", () => {
    expect(ucs.map((uc) => uc.id).sort()).toEqual(["uc1", "uc2", "uc3"]);
    for (const uc of ucs) expect(uc.route).toBe(`/${uc.id}`);
    expect(ucs.filter((uc) => uc.bewertet).map((uc) => uc.id)).toEqual(["uc3"]);
  });
});
