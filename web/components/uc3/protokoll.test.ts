import { eintragSchema } from "@kic/ui/shell";
import { describe, expect, it } from "vitest";
import { eintragAus, type ProtokollZeile } from "./protokoll";

// Erfundene Daten: Vorschlag des Klassifikations-Agenten, Beamte zählen nicht mehr mit (Regelsatz v3).
const vorschlag: ProtokollZeile = {
  id: 30,
  zeit: "2026-11-06T06:28:00Z",
  uc: "uc3",
  akteur: "agent",
  name: "agent.klassifikation",
  anweisung: "Beamte zählen nicht mehr mit",
  wirkung: "Regelsatz v3: neue Regel R6_beschaeftigungskategorie_ohne_beamte",
  status: "freigegeben",
  modell: null,
  provider: null,
  ref: null,
  rolle: "klassifikation",
  typ: "regel_neu",
  regelsatz_ziel: "v3",
  aenderungen: [
    {
      regel: {
        name: "R6_beschaeftigungskategorie_ohne_beamte",
        art: "ausschluss",
        parameter: { merkmal: "beschaeftigungskategorie", werte: ["B"] },
      },
    },
  ],
  freigegeben_von: "Petra Probe",
  freigegeben_am: "2026-11-06T06:32:00Z",
};
const bezeichnungen = { qualifikation: { B: "Beamte" } };

describe("eintragAus", () => {
  it("zeigt bei einem freigegebenen Vorschlag Name, Datum und Uhrzeit in Wiener Zeit und keine Rohnamen", () => {
    const e = eintragAus(vorschlag, bezeichnungen);
    expect(e.wirkung).toContain("\nFreigegeben von Petra Probe, 06.11.2026, 07:32");
    expect(e.wirkung).toContain("Neue Fassung 3: Beschäftigungsverhältnisse mit Kategorie Beamte zählen nicht mehr.");
    expect(e.name).toBe("Klassifikations-Agent");
    const ganz = JSON.stringify(e);
    for (const roh of ["Regelsatz v3", "agent.klassifikation", "R6_beschaeftigungskategorie_ohne_beamte"]) {
      expect(ganz).not.toContain(roh);
    }
    expect(eintragSchema.parse(e)).toEqual(e);
  });

  it("zeigt bei einem abgelehnten Vorschlag, wer abgelehnt hat und wann", () => {
    const e = eintragAus(
      { ...vorschlag, status: "abgelehnt", freigegeben_von: null, freigegeben_am: null, abgelehnt_von: "Petra Probe", abgelehnt_am: "2026-11-06T06:40:00Z" },
      bezeichnungen,
    );
    expect(e.wirkung).toContain("Abgelehnt von Petra Probe, 06.11.2026, 07:40");
    expect(e.wirkung).not.toContain("Freigegeben");
  });

  it("nimmt Name und Zeit aus meta.freigabe, wenn es keine Vorschlagszeile gibt", () => {
    const e = eintragAus({
      ...vorschlag,
      typ: null,
      aenderungen: undefined,
      freigegeben_von: null,
      freigegeben_am: null,
      f_name: "Petra Probe",
      f_zeitpunkt: "2026-11-06T06:32:00Z",
      f_entscheidung: "ja",
    });
    expect(e.wirkung).toBe("Neue Fassung 3: neue Regel R6_beschaeftigungskategorie_ohne_beamte\nFreigegeben von Petra Probe, 06.11.2026, 07:32");
  });

  it("hängt bei einer offenen Zeile keine Entscheidungszeile an", () => {
    const e = eintragAus({ ...vorschlag, status: "offen" }, bezeichnungen);
    expect(e.wirkung).not.toMatch(/Freigegeben von|Abgelehnt von/);
  });

  it("erfindet ohne Namen keine Entscheidungszeile", () => {
    const e = eintragAus({ ...vorschlag, freigegeben_von: null }, bezeichnungen);
    expect(e.wirkung).not.toMatch(/Freigegeben von|Abgelehnt von/);
    expect(e.wirkung).not.toContain("\n");
  });

  it("schreibt „Regelsatz v2 freigeben“ in Anweisung und Wirkung in Wörtern der App", () => {
    const zeile = { ...vorschlag, typ: null, anweisung: "Regelsatz v2 freigeben", wirkung: "Regelsatz v2 freigeben" };
    const e = eintragAus(zeile);
    expect(e.anweisung).toBe("Stand nach den Änderungsaufträgen freigeben");
    expect(e.wirkung?.split("\n")[0]).toBe("Stand nach den Änderungsaufträgen freigeben");
    expect(eintragAus({ ...zeile, anweisung: "Regelsatz v1 freigeben" }).anweisung).toBe("Alte Regeln freigeben");
  });

  it("schreibt „Regelsatz pensionen-v1 freigeben“ in Wörtern der App", () => {
    const zeile = { ...vorschlag, typ: null, anweisung: "Regelsatz pensionen-v1 freigeben", wirkung: "Regelsatz pensionen-v1 freigeben" };
    const e = eintragAus(zeile);
    expect(e.anweisung).toBe("Regeln für die Pensionen freigeben");
    expect(e.wirkung?.split("\n")[0]).toBe("Regeln für die Pensionen freigeben");
    expect(JSON.stringify(e)).not.toContain("pensionen-v1");
  });

  it("lässt den Wortlaut eines Auftrags wörtlich stehen", () => {
    const auftrag = "Auftrag 1: Ziel ist der neue Regelsatz v2, Regelsatz v1 bleibt, wie er ist.";
    expect(eintragAus({ ...vorschlag, anweisung: auftrag }, bezeichnungen).anweisung).toBe(auftrag);
  });

  it("schreibt die festen Sätze des Programms mit Monatsnamen und den Wörtern der App", () => {
    const zeile = { ...vorschlag, typ: null, wirkung: null };
    expect(eintragAus({ ...zeile, anweisung: "Berichtsmonat 2026-07 (v1) veröffentlichen" }).anweisung).toBe(
      "Berichtsmonat Juli 2026 (Alte Regeln) veröffentlichen",
    );
    expect(eintragAus({ ...zeile, anweisung: "Ministeriums-Lieferung 2026-07 freigeben (Auftrag 3)" }).anweisung).toBe(
      "Ministeriums-Lieferung Juli 2026 freigeben (Auftrag 3)",
    );
  });

  it("schreibt „nach Regelsatz v1“ im Satz eines Vorschlags als „nach den alten Regeln“", () => {
    const e = eintragAus({
      ...vorschlag,
      regelsatz_ziel: "ministerium",
      aenderungen: [{ regel: { name: "M01", art: "zaehl", beschreibung: "Je Tag gilt die jüngste Lieferung nach Regelsatz v1." } }],
    });
    expect(e.wirkung?.split("\n")[0]).toBe("Ministeriums-Lieferung: Je Tag gilt die jüngste Lieferung nach den alten Regeln.");
  });

  it("wiederholt Name und Zeit nicht, wenn derselbe Mensch angewiesen und freigegeben hat", () => {
    const mensch: ProtokollZeile = {
      ...vorschlag,
      akteur: "mensch",
      name: "Petra Probe",
      typ: null,
      wirkung: "37 Regeln mit Namen freigegeben",
      freigegeben_von: null,
      freigegeben_am: null,
      f_name: "Petra Probe",
      f_zeitpunkt: "2026-11-06T06:32:00Z",
      f_entscheidung: "ja",
    };
    expect(eintragAus(mensch).wirkung).toBe("37 Regeln mit Namen freigegeben");
    expect(eintragAus({ ...mensch, f_name: "Paul Prüfer" }).wirkung).toBe(
      "37 Regeln mit Namen freigegeben\nFreigegeben von Paul Prüfer, 06.11.2026, 07:32",
    );
  });

  it("zeigt keinen Namen aus einer Entscheidung, die nicht zum Status passt", () => {
    const e = eintragAus({
      ...vorschlag,
      typ: null,
      wirkung: null,
      freigegeben_von: null,
      freigegeben_am: null,
      f_name: "Petra Probe",
      f_zeitpunkt: "2026-11-06T06:32:00Z",
      f_entscheidung: "nein",
    });
    expect(e.wirkung).toBeNull();
  });

  it("schreibt eine Zeit kurz nach Mitternacht als 00:05 am Wiener Kalendertag", () => {
    const e = eintragAus({ ...vorschlag, typ: null, wirkung: null, freigegeben_am: "2026-11-05T23:05:00Z" });
    expect(e.wirkung).toBe("Freigegeben von Petra Probe, 06.11.2026, 00:05");
  });

  it("zeigt ohne sonstige Wirkung nur die Entscheidungszeile", () => {
    const e = eintragAus({ ...vorschlag, typ: null, wirkung: null });
    expect(e.wirkung).toBe("Freigegeben von Petra Probe, 06.11.2026, 07:32");
  });
});
