import { describe, expect, it } from "vitest";
import {
  abrechnungSatz,
  bestandSatz,
  haltSatz,
  haltTreffer,
  revisionSatz,
  sortiereTreffer,
  trefferTitel,
  ursachenSatz,
  type Treffer,
} from "./lauf-detail";

function treffer(teil: Partial<Treffer>): Treffer {
  return {
    regelId: 1,
    name: "P99_test",
    art: "test",
    beschreibung: "Test.",
    satz: null,
    ebene: "satz",
    anzahl: 1,
    umfang: null,
    beispiele: [],
    einstufung: null,
    massnahme: null,
    anhalten: false,
    belegSql: null,
    ...teil,
  };
}

describe("Lauf-Detail: Sätze", () => {
  // Fehler: eine negative Differenz erscheint als „um -4.410 … kleiner“.
  it("Revision mit negativer Differenz sagt „kleiner“ mit Betrag", () => {
    const satz = revisionSatz({ berichtsmonat: "2025-08", veroeffentlicht: 393712, aktuell: 389302, differenz: -4410, statusVorher: "vorlaeufig" });
    expect(satz).toContain("August 2025 um 4.410 Verhältnisse kleiner als bisher gezeigt (389.302 statt 393.712)");
    expect(satz).not.toContain("-");
  });

  // Fehler: „1 Verhältnisse“ und „ist/sind“ falsch im Singular.
  it("Singular bei genau einem Verhältnis", () => {
    expect(revisionSatz({ berichtsmonat: "2025-02", veroeffentlicht: 10, aktuell: 11, differenz: 1, statusVorher: "endgueltig" })).toContain(
      "um 1 Verhältnis größer als veröffentlicht",
    );
    expect(ursachenSatz([{ ursache: "nicht_mehr_enthalten", anzahl: 1 }, { ursache: "merkmal_geaendert", anzahl: 0 }])).toBe(
      "Gründe: 1 Verhältnis ist in der neuen Lieferung nicht mehr enthalten.",
    );
  });

  // Fehler: die Abrechnung nimmt den Bestand samt Fortgeschriebenen und geht dann nicht auf.
  it("Abrechnung zählt ohne die aus dem Vormonat übernommenen Verhältnisse", () => {
    expect(abrechnungSatz({ gelesen: 345078, gezaehlt: 390900, fortgeschrieben: 77746, nichtGezaehlt: 31924, ausgeschlossen: 0 })).toBe(
      "345.078 gelesene Sätze = 313.154 gezählt + 31.924 nicht gezählt + 0 ausgeschlossen.",
    );
  });

  // Fehler: Rückgang zum Vormonat erscheint als „-12 mehr“.
  it("Bestand mit Rückgang sagt „weniger“", () => {
    expect(bestandSatz({ lieferung: "2025-03", gezaehlt: 100 }, { lieferung: "2025-02", gezaehlt: 112 })).toBe(
      "Am 31.03.2025 bestanden 100 Beschäftigungsverhältnisse, 12 weniger als im Februar 2025.",
    );
  });
});

describe("Lauf-Detail: Auffälligkeiten", () => {
  // Fehler: die Überschrift nimmt die Zeilenzahl (größere Anzahl) statt der fehlenden Verhältnisse.
  it("Überschrift eines angehaltenen Monats nimmt die fehlenden Verhältnisse", () => {
    const liste = [
      treffer({ art: "zeilenzahl_vs_vormonat", anzahl: 89026, anhalten: true }),
      treffer({ art: "verhaeltnisse_verschwunden", anzahl: 78949, anhalten: true }),
      treffer({ art: "sprung_aggregat", anzahl: 2 }),
    ];
    const t = haltTreffer(liste);
    expect(t && haltSatz(t, "2025-10")).toBe(
      "Im Oktober 2025 fehlen 78.949 Verhältnisse des Vormonats, deshalb ist der Monat angehalten.",
    );
  });

  // Fehler: anhaltende Treffer rutschen hinter große Zählungen; Treffer mit 0 erscheinen.
  it("ordnet anhaltend, dann nicht erklärbar, dann Anzahl; ohne Treffer mit 0", () => {
    const sortiert = sortiereTreffer([
      treffer({ name: "a", anzahl: 2000, einstufung: "erklaert-plausibel" }),
      treffer({ name: "b", anzahl: 5, einstufung: "nicht-erklaerbar" }),
      treffer({ name: "c", anzahl: 2, anhalten: true, einstufung: "erklaert-datenproblem" }),
      treffer({ name: "d", anzahl: 0, einstufung: "nicht-erklaerbar" }),
    ]);
    expect(sortiert.map((t) => t.name)).toEqual(["c", "b", "a"]);
  });

  // Fehler: Platzhalter der Satzvorlage bleiben roh stehen.
  it("füllt die Satzvorlage der Regel", () => {
    expect(trefferTitel(treffer({ satz: "In {monat} fehlen {anzahl} ({umfang}).", anzahl: 1234, umfang: "x" }), "2025-10")).toBe(
      "In Oktober 2025 fehlen 1.234 (x).",
    );
  });
});
