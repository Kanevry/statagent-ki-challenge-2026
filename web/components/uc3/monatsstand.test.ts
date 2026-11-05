import { describe, expect, it } from "vitest";
import { monatsStand, vormonatIn } from "./monatsstand";

describe("vormonatIn", () => {
  it("vergleicht nur mit dem Kalender-Vormonat, nie mit einem früheren Monat über eine Lücke", () => {
    const monate = [{ lieferung: "2025-01" }, { lieferung: "2025-03" }];
    expect(vormonatIn({ lieferung: "2025-03" }, monate)).toBe("Vormonat fehlt");
    expect(vormonatIn({ lieferung: "2025-01" }, monate)).toBe("erster Monat");
  });

  it("findet den Vormonat über den Jahreswechsel", () => {
    expect(vormonatIn({ lieferung: "2025-01" }, [{ lieferung: "2024-12" }, { lieferung: "2025-01" }])).toEqual({
      lieferung: "2024-12",
    });
  });
});

describe("monatsStand", () => {
  it("zeigt bei einem angehaltenen Monat auch „vorläufig“ (Review !51 Punkt 7)", () => {
    expect(monatsStand({ angehalten: true, ergebnisStand: "vorlaeufig", gehtAuf: true })).toEqual({
      art: "warnung",
      wort: "angehalten, vorläufig",
    });
  });

  it("meldet eine nicht aufgehende Abrechnung vor jedem anderen Stand", () => {
    expect(monatsStand({ angehalten: true, ergebnisStand: "endgueltig", gehtAuf: false }).art).toBe("fehler");
  });
});
