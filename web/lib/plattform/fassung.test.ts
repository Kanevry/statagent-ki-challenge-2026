import { describe, expect, it } from "vitest";
import { fassungAus } from "./fassung";

describe("fassungAus", () => {
  it("ohne Wert kein Knopf, auch bei leerer Zeile", () => {
    expect(fassungAus({})).toBeNull();
    expect(fassungAus({ KIC_LIVE_ADRESSE: "  " })).toBeNull();
  });

  it("nimmt nur eine https-Adresse ohne Zugangsdaten", () => {
    expect(fassungAus({ KIC_LIVE_ADRESSE: "http://live.example.org" })).toBeNull();
    expect(fassungAus({ KIC_LIVE_ADRESSE: "javascript:alert(1)" })).toBeNull();
    expect(fassungAus({ KIC_LIVE_ADRESSE: "https://nutzer:geheim@live.example.org" })).toBeNull();
    expect(fassungAus({ KIC_LIVE_ADRESSE: "https://live.example.org/pfad" })).toEqual({
      adresse: "https://live.example.org",
      art: "live",
    });
  });

  it("die Vorführ-Instanz zeigt zurück auf die öffentliche Fassung", () => {
    expect(
      fassungAus({ KIC_OEFFENTLICHE_ADRESSE: "https://demo.example.org", KIC_LIVE_ADRESSE: "https://live.example.org" }),
    ).toEqual({ adresse: "https://demo.example.org", art: "oeffentlich" });
  });
});
