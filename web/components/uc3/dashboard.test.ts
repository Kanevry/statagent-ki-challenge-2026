import { describe, expect, it } from "vitest";
import { balkenProzent, einstufungsReihe, kopfSatz, sqlEinstufungen, sqlGeschlecht, vorlaeufigSatz } from "./dashboard";

const monat = (lieferung: string, ergebnisStand: "endgueltig" | "vorlaeufig", angehalten = false) => ({ lieferung, ergebnisStand, angehalten });

describe("kopfSatz", () => {
  it("zählt alte Regeln: veröffentlicht und angehalten", () => {
    const monate = [monat("2025-09", "endgueltig"), monat("2025-10", "vorlaeufig", true), monat("2025-11", "endgueltig")];
    expect(kopfSatz(monate)).toBe("3 Monate gerechnet: 2 veröffentlicht, 1 angehalten.");
  });
  it("nennt angehaltene nicht zusätzlich als vorläufig", () => {
    const monate = [monat("2025-09", "vorlaeufig"), monat("2025-10", "vorlaeufig", true)];
    expect(kopfSatz(monate)).toBe("2 Monate gerechnet: 1 vorläufig, 1 angehalten.");
  });
});

describe("vorlaeufigSatz", () => {
  it("nennt wenige Monate beim Namen", () => {
    const monate = [monat("2025-03", "vorlaeufig"), monat("2025-04", "endgueltig"), monat("2025-10", "vorlaeufig")];
    expect(vorlaeufigSatz(monate)).toBe("März 2025 und Oktober 2025 sind noch nicht veröffentlicht.");
  });
  it("fasst zusammen, wenn kein Monat veröffentlicht ist", () => {
    expect(vorlaeufigSatz([monat("2025-03", "vorlaeufig")])).toBe("Mit diesen Regeln ist noch kein Monat veröffentlicht.");
  });
  it("sagt, wenn alle veröffentlicht sind", () => {
    expect(vorlaeufigSatz([monat("2025-03", "endgueltig")])).toBe("Alle Monate sind veröffentlicht.");
  });
});

describe("einstufungsReihe", () => {
  it("hält die Reihenfolge, füllt Fehlendes mit 0 und zählt Leeres als nicht erklärbar", () => {
    const reihe = einstufungsReihe([
      { einstufung: "erklaert-plausibel", anzahl: "78" },
      { einstufung: null, anzahl: "2" },
      { einstufung: "nicht-erklaerbar", anzahl: 38 },
    ]);
    expect(reihe.map((e) => [e.code, e.anzahl])).toEqual([
      ["nicht-erklaerbar", 40],
      ["erklaert-datenproblem", 0],
      ["erklaert-plausibel", 78],
    ]);
  });
});

describe("Belege", () => {
  const lauf = { lieferung: "2026-07", regelsatz: "v1", regelstand: "abc", zeitraumArt: "Stichtag" as const };
  it("sqlGeschlecht filtert den Regelstand, sonst zählt ein neu gerechneter Monat doppelt", () => {
    expect(sqlGeschlecht(lauf)).toContain("s.regelstand = 'abc'");
    expect(sqlGeschlecht(lauf)).toContain("s.zeitraum_art = 'Stichtag'");
  });
  it("sqlEinstufungen nimmt je Monat den maßgeblichen Lauf", () => {
    const text = sqlEinstufungen("v2");
    expect(text).toContain("regelsatz = 'v2'");
    expect(text).toContain("t.lauf_id = m.quelle_id");
  });
});

describe("balkenProzent", () => {
  it("rechnet von null aus und übersteht leere Gruppen", () => {
    expect(balkenProzent(50, 200)).toBe(25);
    expect(balkenProzent(0, 0)).toBe(0);
  });
});
