import { describe, expect, it } from "vitest";
import { oenaceWechsel, wechselSaetze, wechselTitel } from "./oenace-wechsel";

describe("Wechsel der ÖNACE auf der Monatsseite", () => {
  // Fehler: Der Absatz stünde auf jedem Monat oder fehlte unter v2.
  it("gilt nur im Monat des Wechsels, in beiden Regelsätzen", () => {
    expect(oenaceWechsel("2025-02", "v1")).toBeNull();
    expect(oenaceWechsel("2025-01", "v3")).toBeNull();
    expect(oenaceWechsel("2025-01", "v1")).not.toBeNull();
    expect(oenaceWechsel("2025-01", "v2")).not.toBeNull();
  });

  // Fehler: Monate als „2024-12“ oder Zahlen ohne Tausenderpunkt im sichtbaren Satz.
  it("nennt Fassungen, Monate und Zahlen lesbar", () => {
    const w = oenaceWechsel("2025-01", "v1")!;
    expect(wechselTitel(w)).toBe("Ab diesem Monat gilt ÖNACE 2025 statt ÖNACE 2008.");
    expect(wechselSaetze(w, "2025-01")[1]).toContain(
      "Von 386.299 Beschäftigungsverhältnissen, die am 31. Dezember 2024 in beiden Lieferungen stehen, tragen 189.170 in der Lieferung Jänner 2025 einen anderen Abschnitt als in der Lieferung Dezember 2024.",
    );
  });
});
