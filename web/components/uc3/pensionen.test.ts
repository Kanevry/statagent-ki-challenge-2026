import { describe, expect, it } from "vitest";
import { fehltSaetze, pensionsdaten, pensionsZeilen, pruefSatz, zusammenlegungSatz } from "./pensionen";

const wert = (jahr: number, traeger: string, wert: string | number, tabelle = "T12") => ({ jahr, tabelle, traeger, wert, vorlaeufig: true });
const traeger = (code: string, ebene: number, uebergeordnet: string | null) => ({ code, bezeichnung: `Name ${code}`, ebene, uebergeordnet });

const GLIEDERUNG = [
  traeger("INSG", 1, null),
  traeger("PV-SEL", 2, "INSG"),
  traeger("SVA", 3, "PV-SEL"),
  traeger("SVS", 3, "PV-SEL"),
  traeger("SVS-GW", 4, "SVS"),
  traeger("BVA", 3, "PV-SEL"),
];

describe("pensionsZeilen", () => {
  // Fängt: Ein Jahr ohne Meldung wird zur 0, und ein abgelöster Träger sieht aus, als hätte er keine Pensionen.
  it("bildet Summen vor ihren Teilen und lässt Jahre ohne Meldung leer", () => {
    const zeilen = pensionsZeilen(GLIEDERUNG, [wert(2019, "SVA", "195549"), wert(2020, "SVS-GW", "201823")], [2019, 2020]);
    expect(zeilen.map((z) => [z.code, z.werte])).toEqual([
      ["INSG", [195549, 201823]],
      ["PV-SEL", [195549, 201823]],
      ["SVA", [195549, null]],
      ["SVS", [null, 201823]],
      ["SVS-GW", [null, 201823]],
    ]);
  });

  it("nennt das Kürzel nur bei den Trägern", () => {
    const zeilen = pensionsZeilen(GLIEDERUNG, [wert(2020, "SVS-GW", 1)], [2020]);
    expect(zeilen.map((z) => z.name)).toEqual(["Name INSG", "Name PV-SEL", "Name SVS (SVS)", "Name SVS-GW"]);
  });
});

describe("Sätze aus den Daten", () => {
  it("schreibt die Zusammenlegung aus den Übergängen", () => {
    const zeilen = [
      { code_alt: "BVA", code_neu: "BVAEB", gueltig_ab: "2020-01-01" },
      { code_alt: "VAEB", code_neu: "BVAEB", gueltig_ab: "2020-01-01" },
      { code_alt: "SVA", code_neu: "SVS", gueltig_ab: "2020-01-01" },
      { code_alt: "SVB", code_neu: "SVS", gueltig_ab: "2020-01-01" },
      { code_alt: "VAN", code_neu: "SVS", gueltig_ab: "2020-01-01" },
    ];
    expect(zusammenlegungSatz(zeilen)).toBe(
      "Zum 1. Jänner 2020 wurden Träger zusammengelegt. Aus BVA und VAEB wurde die BVAEB, aus SVA, SVB und VAN die SVS. Die Zahlen davor und danach stehen unverändert nebeneinander.",
    );
    expect(zusammenlegungSatz([])).toBeNull();
  });

  // Fängt: Die Seite behauptet eine Lücke, die es in dieser Datenbank nicht (mehr) gibt.
  it("nennt nur Lücken, die in den Daten stehen", () => {
    const voll = [wert(2020, "BVAEB-EB", 1), wert(2018, "VAN", 1), wert(2019, "VAN", 1)];
    const saetze = fehltSaetze(voll);
    expect(saetze[0]).toContain("Öffentlich Bedienstete fehlen in allen Jahren");
    expect(saetze[1]).toBe("Bei den vorzeitigen Alterspensionen fehlt 2018 und 2019 das Notariat (VAN), es meldet diese Art nicht.");
    expect(fehltSaetze([...voll, wert(2019, "BVA", 1), wert(2019, "VAN", 1, "T13")])).toEqual([]);
  });

  it("sagt, was beim Laden nachgerechnet wurde, auch wenn etwas abweicht", () => {
    const ladung = { dateien: "28", formate: "9", summen: "394", abweichend: "0", freigegeben_von: null, freigegeben_am: null };
    expect(pruefSatz(ladung)).toBe("28 Dateien in 9 Formaten gelesen. 394 Summen aus den Dateien nachgerechnet, keine weicht ab.");
    expect(pruefSatz({ ...ladung, abweichend: "2" })).toContain("2 weichen ab");
    expect(pruefSatz({ ...ladung, dateien: 0 })).toBeNull();
    expect(pruefSatz(undefined)).toBeNull();
  });
});

describe("pensionsdaten", () => {
  it("zeigt den Stand der Datenbank: vorläufig oder freigegeben mit Namen", () => {
    const tabellen = [{ code: "T12", bezeichnung: "Stand" }];
    const ladung = { dateien: 1, formate: 1, summen: 1, abweichend: 0, freigegeben_von: "Anna Beispiel", freigegeben_am: "2026-11-05" };
    expect(pensionsdaten([wert(2020, "SVS-GW", 1)], GLIEDERUNG, tabellen, [], undefined).vorlaeufig).toBe(true);
    const frei = pensionsdaten([{ ...wert(2020, "SVS-GW", 1), vorlaeufig: false }], GLIEDERUNG, tabellen, [], ladung);
    expect(frei.vorlaeufig).toBe(false);
    expect(frei.freigabe).toEqual({ name: "Anna Beispiel", am: "2026-11-05" });
  });

  // Fängt: Der Leerzustand vor dem Laden kippt in eine Tabelle ohne Zeilen.
  it("bleibt ohne Zeilen leer", () => {
    const leer = pensionsdaten([], GLIEDERUNG, [{ code: "T12", bezeichnung: "Stand" }], [], undefined);
    expect(leer.tabellen).toEqual([]);
    expect(leer.jahre).toEqual([]);
    expect(leer.zusammenlegung).toBeNull();
  });
});
