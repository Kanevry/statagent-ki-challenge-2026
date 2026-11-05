import { describe, expect, it } from "vitest";
import {
  abrechnungSatz,
  bestandSatz,
  einstufungStatus,
  fehlendeGruppen,
  haltSatz,
  haltTreffer,
  hatRevisionsbedarf,
  kannVeroeffentlichen,
  massnahmeSatz,
  regelsatzAus,
  revisionSatz,
  sortiereTreffer,
  trefferTitel,
  ursachenSatz,
  weiterSatz,
  type Treffer,
  rohAlsSatz,
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
    expect(satz).toContain("August 2025 um 4.410 Beschäftigungsverhältnisse kleiner als bisher gezeigt (389.302 statt 393.712)");
    expect(satz).not.toContain("-");
  });

  // Fehler: „1 Verhältnisse“ und „ist/sind“ falsch im Singular.
  it("Singular bei genau einem Verhältnis", () => {
    expect(revisionSatz({ berichtsmonat: "2025-02", veroeffentlicht: 10, aktuell: 11, differenz: 1, statusVorher: "endgueltig" })).toContain(
      "um 1 Beschäftigungsverhältnis größer als veröffentlicht",
    );
    expect(ursachenSatz([{ ursache: "nicht_mehr_enthalten", anzahl: 1 }, { ursache: "merkmal_geaendert", anzahl: 0 }])).toBe(
      "Gründe: 1 Beschäftigungsverhältnis ist in der neuen Lieferung nicht mehr enthalten.",
    );
  });

  // Fehler: die Abrechnung nimmt den Bestand samt Fortgeschriebenen und geht dann nicht auf.
  it("Abrechnung zählt ohne die aus dem Vormonat übernommenen Verhältnisse", () => {
    expect(abrechnungSatz({ gelesen: 345078, gezaehlt: 390900, fortgeschrieben: 77746, nichtGezaehlt: 31924, ausgeschlossen: 0 })).toBe(
      "345.078 gelesene Zeilen = 313.154 gezählt + 31.924 nicht gezählt + 0 ausgeschlossen.",
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
      treffer({ art: "verhaeltnisse_verschwunden", anzahl: 78949, anhalten: true, details: { anteil: 0.200277, rueckfrage: "R3" } }),
      treffer({ art: "sprung_aggregat", anzahl: 2 }),
    ];
    const t = haltTreffer(liste);
    expect(t && haltSatz(t, "2025-10")).toBe(
      "Im Oktober 2025 fehlt jedes fünfte Beschäftigungsverhältnis aus dem September 2025, zusammen 78.949. Deshalb ist der Monat angehalten.",
    );
  });

  // Fehler (Sichtprüfung bb, #18): März nannte „2 Gruppen“ ohne Namen, P16 dieselben 1.492 „Einzelfälle wie Stornos“,
  // und jede anhaltende Prüfung nannte eine andere Bedingung zum Weitergehen.
  it("März: fehlende freie Dienstverträge mit Namen, P16 rechnet sie heraus, ein Haltesatz je Rückfrage", () => {
    const p13 = treffer({
      name: "P13_auspraegung_verschwunden",
      art: "auspraegung_verschwunden",
      anzahl: 2,
      anhalten: true,
      details: {
        rueckfrage: "R4",
        auspraegungen: [
          { code: "AngestellteFD", gliederung: "qualifikation", aktuell: 0, vormonat: 1131 },
          { code: "ArbeiterFD", gliederung: "qualifikation", aktuell: 0, vormonat: 361 },
        ],
      },
    });
    expect(haltSatz(p13, "2025-03", ["AngestellteFD", "ArbeiterFD"])).toBe(
      "Im März 2025 fehlen alle freien Dienstverträge (Februar 2025: 1.492). Deshalb ist der Monat angehalten.",
    );
    const gruppen = fehlendeGruppen([p13], ["AngestellteFD", "ArbeiterFD"]);
    expect(
      massnahmeSatz(
        { name: "P16_verhaeltnisse_verschwunden", massnahme: "keine (Einzelfälle, z. B. Stornos)", einstufung: "erklaert-plausibel", anhalten: false },
        { fehlendeGruppen: gruppen },
      ),
    ).toBe("1.492 davon sind die fehlenden freien Dienstverträge, die übrigen sind Einzelfälle wie Stornos.");
    const halt = (name: string) =>
      massnahmeSatz({ name, massnahme: "Monat angehalten", einstufung: "erklaert-datenproblem", anhalten: true, details: { rueckfrage: "R3" } });
    expect(new Set(["P15_x", "P16_x", "P17_x"].map(halt))).toEqual(
      new Set(["Der Monat ist angehalten, bis die Fachabteilung Rückfrage R3 beantwortet."]),
    );
    // Fehler (Review !77, Punkt 2): fehlt nur ArbeiterFD, stand trotzdem „alle freien Dienstverträge“.
    const nurArbeiter = treffer({
      art: "auspraegung_verschwunden",
      anzahl: 1,
      anhalten: true,
      details: { auspraegungen: [{ code: "ArbeiterFD", gliederung: "qualifikation", aktuell: 0, vormonat: 361 }] },
    });
    expect(haltSatz(nurArbeiter, "2025-03", ["AngestellteFD", "ArbeiterFD"])).toBe(
      "Im März 2025 fehlen freie Dienstverträge, im Februar 2025 waren es 361 (ArbeiterFD). Deshalb ist der Monat angehalten.",
    );
    expect(weiterSatz({ lieferung: "2025-10", fortgeschrieben: 77746 }, ["R3"])).toBe(
      "Wir übernehmen 77.746 Beschäftigungsverhältnisse aus der Lieferung September 2025 (Regel E07). Der Monat bleibt vorläufig, bis die Fachabteilung Rückfrage R3 beantwortet.",
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

describe("massnahmeSatz und einstufungStatus", () => {
  // Fehler: eine Regel ohne eigenen Satz verliert ihre Maßnahme oder zeigt den Pfeil des Rohtexts.
  it("fällt bei unbekannter Regel auf den Rohtext als Satz zurück", () => {
    const t = { name: "P99_neu", massnahme: "→ C (Umsteiger)", einstufung: null, anhalten: false };
    expect(massnahmeSatz(t)).toBe("Zugeordnet zu C (Umsteiger)");
  });

  // Fehler: eine nicht erklärbare Auffälligkeit mit offener Rückfrage liest sich als Alarm ohne Grund.
  it("nennt die offene Rückfrage bei nicht erklärbar", () => {
    expect(einstufungStatus("nicht-erklaerbar", ["R8"])).toEqual({
      art: "warnung",
      wort: "nicht erklärbar, wartet auf Antwort der Fachabteilung (R8)",
    });
    expect(einstufungStatus("nicht-erklaerbar", []).art).toBe("fehler");
    // Fehler: ohne Einstufung stand „noch nicht eingestuft“, der Qualitätsbericht zählt sie als nicht erklärbar.
    expect(einstufungStatus(null)).toEqual({ art: "fehler", wort: "nicht erklärbar" });
  });
});

describe("Lauf-Detail: Regelsatz, Veröffentlichen, Revisionsbedarf", () => {
  // Fehler: ?regelsatz=x oder ?regelsatz=v3 landet ungeprüft in der Abfrage.
  it("lässt nur v1 und v2 zu, alles andere ist v1", () => {
    expect(regelsatzAus("v2")).toBe("v2");
    expect(regelsatzAus(undefined)).toBe("v1");
    expect(regelsatzAus("v3")).toBe("v1");
    expect(regelsatzAus(["v2", "v2"])).toBe("v1");
  });

  // Fehler: angehaltene oder fortgeschriebene Monate (E07) zeigten einen Befehl, den die CLI ablehnt.
  it("zeigt den Befehl nur, wenn die CLI veröffentlichen würde", () => {
    const frei = { regelnOhneFreigabe: 0, regelstandFreigegeben: true };
    const lauf = { ergebnisStand: "vorlaeufig" as const, fortgeschrieben: 0 };
    expect(kannVeroeffentlichen(lauf, false, frei)).toBe(true);
    expect(kannVeroeffentlichen(lauf, true, frei)).toBe(false);
    expect(kannVeroeffentlichen({ ...lauf, fortgeschrieben: 77746 }, false, frei)).toBe(false);
    expect(kannVeroeffentlichen(lauf, false, { ...frei, regelnOhneFreigabe: 1 })).toBe(false);
    expect(kannVeroeffentlichen(lauf, false, { ...frei, regelstandFreigegeben: false })).toBe(false);
  });

  // Fehler: der Bericht zählte Umschichtungen als Revisionsbedarf, das Lauf-Detail nicht.
  it("zählt eine Umschichtung bei gleicher Summe als Revisionsbedarf", () => {
    expect(hatRevisionsbedarf({ differenz: 0, umgeschichtet: true })).toBe(true);
    expect(hatRevisionsbedarf({ differenz: 0, umgeschichtet: false })).toBe(false);
  });
});

describe("massnahmeSatz nach einer Live-Änderung (Review !51 Runde 2, Punkt 4)", () => {
  it("nimmt bei P07 den gespeicherten Text, damit eine neue Altersgrenze nicht als 75 erscheint", () => {
    const satz = massnahmeSatz({
      name: "P07_alter_hoch_plausibel",
      massnahme: "gezählt, Zeile 80 u. mehr",
      einstufung: "erklaert-plausibel",
      anhalten: false,
    });
    expect(satz).toBe("Gezählt, Zeile 80 und mehr.");
  });

  it("entfernt Regelkürzel in Klammern aus dem gespeicherten Text", () => {
    expect(
      rohAlsSatz(
        "Geburtstag unbekannt: 1. Juli des Geburtsjahres als Ersatztag (R5 ersatz:07-01), Alter in vollendeten Jahren am Stichtag (E03, R5)",
      ),
    ).toBe("Geburtstag unbekannt: 1. Juli des Geburtsjahres als Ersatztag, Alter in vollendeten Jahren am Stichtag.");
  });
});
