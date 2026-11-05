import { describe, expect, it } from "vitest";
import { annahmeSatz, befundSatz, einstufungAus, ersterSatz, rueckfrageBetrifft } from "./bericht";

describe("einstufungAus", () => {
  // Fehler: ein Treffer ohne Einstufung ('' in meta.pruefung_treffer) erschiene grün oder gar nicht; der
  // Generator führt ihn als „nicht erklärbar“.
  it("führt fehlende und unbekannte Codes als nicht erklärbar", () => {
    expect(einstufungAus("")).toMatchObject({ art: "fehler", wort: "nicht erklärbar" });
    expect(einstufungAus(null).code).toBe("nicht-erklaerbar");
    expect(einstufungAus("erklaert-datenproblem")).toMatchObject({ art: "warnung", wort: "erklärt, Datenproblem" });
  });
});

describe("ersterSatz", () => {
  // Fehler: „z. B.“ oder „§ 4 Nr. 1“ beenden den Satz, die Annahme bricht mitten im Gedanken ab.
  it("schneidet nicht an Abkürzungen", () => {
    expect(ersterSatz("Ein ENDE (z. B. 2024-02-30) gilt als Monatsletzter. Sonst bleibt es leer.")).toBe(
      "Ein ENDE (z. B. 2024-02-30) gilt als Monatsletzter.",
    );
    expect(ersterSatz("Fachbeschreibung § 4 Nr. 1, 2, 4. 2024-08: 392.284 Sätze.")).toBe(
      "Fachbeschreibung § 4 Nr. 1, 2, 4. 2024-08: 392.284 Sätze.",
    );
    expect(ersterSatz("Kommt eine Nachlieferung? Wenn nicht: was dann?")).toBe("Kommt eine Nachlieferung?");
  });
});

describe("annahmeSatz", () => {
  // Fehler: Sätze aus meta.annahme, die schon mit „Annahme:“ beginnen, bekämen das Präfix doppelt.
  it("setzt das Präfix genau einmal und schließt den Satz", () => {
    expect(annahmeSatz("Annahme: leere Felder sind unbekannt")).toBe("Annahme: Leere Felder sind unbekannt.");
    expect(annahmeSatz("Wir tauschen beide Felder zurück.")).toBe("Annahme: Wir tauschen beide Felder zurück.");
  });
});

describe("rueckfrageBetrifft", () => {
  const ohne = { nrn: new Set<string>(), regeln: new Set<string>() };
  // Fehler: „und alle weiteren“ träfe nur den ersten Monat (R1 fehlte ab September 2024), und eine Liste
  // zweier Monate würde als Bereich gelesen (R2 erschiene im Oktober 2025).
  it("liest offene Bereiche und einzelne Monate aus `lieferungen`", () => {
    const r1 = { nr: "R1", lieferungen: "lieferung_2024-08 und alle weiteren", regelName: "R5_alter" };
    const r8 = { nr: "R8", lieferungen: "alle ab lieferung_2024-08", regelName: null };
    const r2 = { nr: "R2", lieferungen: "lieferung_2025-05, lieferung_2026-02", regelName: "P18_merkmalswelle" };
    expect(rueckfrageBetrifft(r1, "2025-10", ohne)).toBe(true);
    expect(rueckfrageBetrifft(r8, "2024-08", ohne)).toBe(true);
    expect(rueckfrageBetrifft(r2, "2026-02", ohne)).toBe(true);
    expect(rueckfrageBetrifft(r2, "2025-10", ohne)).toBe(false);
    expect(rueckfrageBetrifft(r2, "2025-10", { nrn: new Set(), regeln: new Set(["P18_merkmalswelle"]) })).toBe(true);
  });
});

describe("befundSatz", () => {
  // Fehler: Platzhalter der Satzvorlage blieben stehen oder Zahlen erschienen ohne Tausenderpunkt.
  it("füllt die Vorlage und lässt Unbekanntes stehen", () => {
    const t = { anzahl: 1980, umfang: null, beschreibung: "", regel: "P10", vorlage: "Im {monat} sind {anzahl} Merkmale leer {x}." };
    expect(befundSatz(t, "2025-10")).toBe("Im Oktober 2025 sind 1.980 Merkmale leer {x}.");
  });
});
