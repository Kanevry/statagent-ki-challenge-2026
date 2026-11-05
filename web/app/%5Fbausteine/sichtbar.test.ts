import { bausteineSichtbar } from "./sichtbar";

// Fängt ab: die Musterseite mit erfundenen Inhalten ist im Produktionsbetrieb ohne Schalter erreichbar.
describe("bausteineSichtbar", () => {
  it("verbirgt die Seite in Produktion, außer mit KIC_BAUSTEINE=1", () => {
    expect(bausteineSichtbar({ NODE_ENV: "production" })).toBe(false);
    expect(bausteineSichtbar({ NODE_ENV: "production", KIC_BAUSTEINE: "0" })).toBe(false);
    expect(bausteineSichtbar({ NODE_ENV: "production", KIC_BAUSTEINE: "1" })).toBe(true);
    expect(bausteineSichtbar({ NODE_ENV: "development" })).toBe(true);
  });
});
