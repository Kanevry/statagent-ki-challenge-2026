import { bereiche, findeUc, ucs } from "../src/ucs";

// Vertrag H: genau UC3 ist bewertet, Route passt zur ID, kein Status-Feld mehr (Lead-Entscheid 58).
// Fängt einen Eintrag ab, der sich versehentlich als „bewertet“ markiert, die Route verbiegt oder den
// entfallenen Status-Filter wieder einführt, den UC-Lanes dann pflegen müssten.
describe("UC-Registry", () => {
  it("hat drei UCs und den Einstieg uc4 mit passender Route und genau einem bewerteten", () => {
    expect(bereiche.map((uc) => uc.id)).toEqual(["uc3", "uc1", "uc2", "uc4"]);
    for (const uc of bereiche) expect(uc.route).toBe(`/${uc.id}`);
    expect(bereiche.filter((uc) => uc.bewertet).map((uc) => uc.id)).toEqual(["uc3"]);
  });

  it("führt nur die Felder des Vertrags, ohne status", () => {
    for (const uc of bereiche) expect(Object.keys(uc).sort()).toEqual(["bewertet", "id", "kurz", "name", "route"]);
  });
});

// Fängt ab: der gemeinsame Einstieg rutscht in die Liste der drei Use Cases (Landing-Texte, Fallback-Route).
it("ucs sind genau die drei Use Cases, uc4 steht nur in bereiche", () => {
  expect(ucs.map((uc) => uc.id)).toEqual(["uc3", "uc1", "uc2"]);
  expect(findeUc("uc4").name).toBe("Gemeinsamer Einstieg");
});
