import { modellQuelleFuer, zeigtDemoHinweis } from "./shell-rahmen";

it("die Probierseite zeigt das Modell der Plattform, die Aufzeichnung den UC2-Bereich", () => {
  expect(modellQuelleFuer("/uc2/frage")).toBeUndefined();
  expect(modellQuelleFuer("/uc2")).toBe("/api/uc2/modell");
  expect(modellQuelleFuer("/uc2/panel")).toBe("/api/uc2/modell");
  expect(modellQuelleFuer("/uc4")).toBeUndefined();
});

it("der Hinweis zum Abbau der KI-Zugänge steht in der App, nicht auf der Startseite (eigener Platz im Hero) und nicht auf den Folien", () => {
  expect(zeigtDemoHinweis("/uc4")).toBe(true);
  expect(zeigtDemoHinweis("/uc3/fragen")).toBe(true);
  expect(zeigtDemoHinweis("/")).toBe(false);
  expect(zeigtDemoHinweis("/praesentation/management")).toBe(false);
});
