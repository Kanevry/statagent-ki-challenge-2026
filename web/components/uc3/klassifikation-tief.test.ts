import { describe, expect, it } from "vitest";
import { anfrageAus, auswahlAus, ebeneWort, oenaceSaetze, regionSaetze, standName, type UebergangZeile } from "./klassifikation-tief";

function zeile(teil: Partial<UebergangZeile>): UebergangZeile {
  return {
    version_alt: "2014-01-01",
    code_alt: "60301",
    name_alt: "Albersdorf",
    version_neu: "2015-01-01",
    code_neu: "60345",
    name_neu: "Gleisdorf",
    ...teil,
  };
}

describe("anfrageAus", () => {
  const anfrage = (text: string) => anfrageAus(new URLSearchParams(text));

  it("versteht oberste Ebene, Kinder und Suche", () => {
    expect(anfrage("art=oenace&fassung=2025")).toEqual({ art: "oenace", fassung: "2025", was: "wurzel" });
    expect(anfrage("art=oenace&fassung=2025&unter=C%2010.1")).toEqual({ art: "oenace", fassung: "2025", was: "kinder", unter: "C 10.1" });
    expect(anfrage("art=region&fassung=2026-01-01&suche=%20Innsbruck%20")).toEqual({
      art: "region",
      fassung: "2026-01-01",
      was: "suche",
      suche: "Innsbruck",
    });
  });

  it.each([
    "art=x&fassung=2025",
    "art=oenace&fassung=2026-01-01",
    "art=region&fassung=2025",
    "art=oenace&fassung=2025&suche=%20",
    `art=oenace&fassung=2025&suche=${"x".repeat(61)}`,
    "art=oenace&fassung=2025&unter=C'%3B",
    "art=oenace&fassung=2025&unter=C&suche=x",
    "art=oenace&fassung=2025&suche=a%00b",
  ])("weist %s ab", (text) => {
    expect(anfrage(text)).toBeNull();
  });
});

describe("Namen", () => {
  it("schreibt Ebene und Stand in Worten", () => {
    expect(ebeneWort("5")).toBe("Unterklasse");
    expect(ebeneWort("2", 24)).toBe("Abteilungen");
    expect(ebeneWort("gemeinde", 2)).toBe("Gemeinden");
    expect(standName("2026-01-01")).toBe("1. Jänner 2026");
  });

  it("zeigt die neueste Fassung und den neuesten Stand zuerst", () => {
    const a = auswahlAus(["2008", "2025"], ["2011-01-01", "2026-01-01"]);
    expect(a.oenace.map((w) => w.name)).toEqual(["ÖNACE 2025", "ÖNACE 2008"]);
    expect(a.region[0]).toEqual({ wert: "2026-01-01", name: "Stand 1. Jänner 2026", ort: "im Stand vom 1. Jänner 2026" });
  });
});

describe("regionSaetze", () => {
  const stand2026 = "2026-01-01";

  it("nennt eine Zusammenlegung von der neuen Gemeinde aus", () => {
    const zeilen = [zeile({}), zeile({ code_alt: "60302", name_alt: "Labuch" })];
    expect(regionSaetze("60345", stand2026, zeilen)).toEqual([
      "Seit 1. Jänner 2015 zusammengelegt aus Albersdorf (60301), Labuch (60302).",
    ]);
  });

  it("nennt dieselbe Zusammenlegung von der alten Gemeinde aus", () => {
    expect(regionSaetze("60301", "2014-01-01", [zeile({})])).toEqual(["Ab 1. Jänner 2015 gehört das zu Gleisdorf (60345)."]);
  });

  it("nennt nur den Code, wenn der Name bleibt und der Code wechselt", () => {
    const code = zeile({ name_alt: "Gleisdorf", name_neu: "Gleisdorf" });
    expect(regionSaetze("60345", stand2026, [code])).toEqual(["Seit 1. Jänner 2015 mit diesem Code, davor (60301)."]);
    expect(regionSaetze("60301", "2014-01-01", [code])).toEqual(["Ab 1. Jänner 2015 mit neuem Code (60345)."]);
  });

  it("kürzt lange Listen", () => {
    const zeilen = ["1", "2", "3", "4", "5"].map((n) => zeile({ code_alt: n, name_alt: `G${n}` }));
    expect(regionSaetze("60345", stand2026, zeilen)).toEqual([
      "Seit 1. Jänner 2015 zusammengelegt aus G1 (1), G2 (2), G3 (3) und 2 weitere.",
    ]);
  });

  it("unterscheidet neuen Namen und geändertes Gebiet, wenn der Code bleibt", () => {
    const name = zeile({ code_alt: "60345", name_alt: "Schwanberg", name_neu: "Bad Schwanberg" });
    expect(regionSaetze("60345", stand2026, [name])).toEqual(["Seit 1. Jänner 2015 unter diesem Namen, davor Schwanberg."]);
    const gebiet = zeile({ code_alt: "60345", name_alt: "Gleisdorf", name_neu: "Gleisdorf" });
    expect(regionSaetze("60345", stand2026, [gebiet])).toEqual(["Seit 1. Jänner 2015 mit geändertem Gebiet."]);
  });

  it("sagt nichts über Änderungen, die vom gewählten Stand aus auf der anderen Seite liegen", () => {
    // Stand 2011: Die Gemeinde 60345 entsteht erst 2015; sie wird dort gar nicht angezeigt, darf aber auch keinen Satz bekommen.
    expect(regionSaetze("60345", "2011-01-01", [zeile({})])).toEqual([]);
    // Stand 2026: Die alte Gemeinde 60301 gibt es nicht mehr, ihr Ende liegt vor dem Stand.
    expect(regionSaetze("60301", stand2026, [zeile({})])).toEqual([]);
  });
});

describe("oenaceSaetze", () => {
  const wechsel = (teil: Partial<UebergangZeile>) =>
    zeile({ version_alt: "2008", version_neu: "2025", code_alt: "J 62.01-0", name_alt: "Programmierung", code_neu: "K 62.10-0", name_neu: "Software", ...teil });

  it("schweigt, wenn der Code gleich bleibt", () => {
    const gleich = wechsel({ code_alt: "C 10.11-0", code_neu: "C 10.11-0" });
    expect(oenaceSaetze("C 10.11-0", "2008", [gleich])).toEqual([]);
    expect(oenaceSaetze("C 10.11-0", "2025", [gleich])).toEqual([]);
  });

  it("nennt den neuen und den alten Code", () => {
    expect(oenaceSaetze("J 62.01-0", "2008", [wechsel({})])).toEqual(["Ab ÖNACE 2025 heißt der Code Software (K 62.10-0)."]);
    expect(oenaceSaetze("K 62.10-0", "2025", [wechsel({})])).toEqual(["In ÖNACE 2008 war das Programmierung (J 62.01-0)."]);
  });

  it("nennt eine Teilung, auch wenn ein Ziel den alten Code behält", () => {
    const zeilen = [wechsel({ code_neu: "J 62.01-0", name_neu: "A" }), wechsel({ code_neu: "K 62.10-0", name_neu: "B" })];
    expect(oenaceSaetze("J 62.01-0", "2008", zeilen)).toEqual(["Ab ÖNACE 2025 aufgeteilt auf A (J 62.01-0), B (K 62.10-0)."]);
  });
});
