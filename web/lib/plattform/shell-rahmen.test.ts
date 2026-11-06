import { modellQuelleFuer } from "./shell-rahmen";

it("die Probierseite zeigt das Modell der Plattform, die Aufzeichnung den UC2-Bereich", () => {
  expect(modellQuelleFuer("/uc2/frage")).toBeUndefined();
  expect(modellQuelleFuer("/uc2")).toBe("/api/uc2/modell");
  expect(modellQuelleFuer("/uc2/panel")).toBe("/api/uc2/modell");
  expect(modellQuelleFuer("/uc4")).toBeUndefined();
});
