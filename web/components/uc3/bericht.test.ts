import { describe, expect, it } from "vitest";
import { annahmeSatz, befundSatz, einstufungAus, ersterSatz, pruefungMalMonat, rueckfrageBetrifft, rueckfragenInAllenMonaten } from "./bericht";

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

  // Fehler: Rückfrage R1 endete im Bericht mit „… mit dem 1.“, weil eine Ordinalzahl den Satz beendete.
  it("schneidet nicht an Ordinalzahlen", () => {
    expect(ersterSatz("Rechnen wir mit dem 1. Tag oder mit dem 15. Juli? Sonst nichts.")).toBe(
      "Rechnen wir mit dem 1. Tag oder mit dem 15. Juli?",
    );
  });
});

describe("rueckfragenInAllenMonaten", () => {
  // Fehler: Der Kopf nannte nur Rückfragen, auf die jeder Monat wartet. R8 hält nur März und Oktober 2025 offen,
  // betrifft aber jeden Monat; R1 betrifft auch jeden Monat, hält aber nichts offen und gehört nicht in den Kopf.
  it("nennt Rückfragen für alle Monate, die irgendwo etwas offen halten", () => {
    const zeilen = [
      { monat: { lieferung: "2024-08" }, wartet: [] },
      { monat: { lieferung: "2025-03" }, wartet: ["R4", "R8"] },
    ];
    const offen = [
      { nr: "R1", titel: "Geburtsmonat 13", lieferungen: "lieferung_2024-08 und alle weiteren" },
      { nr: "R4", titel: "Freie Dienstverträge fehlen", lieferungen: "lieferung_2025-03" },
      { nr: "R8", titel: "Kurze Zweitmeldungen", lieferungen: "alle ab lieferung_2024-08" },
    ];
    expect(rueckfragenInAllenMonaten(zeilen, offen).map((q) => q.nr)).toEqual(["R8"]);
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

describe("ersterSatz nach Zahlen (Review !77, Punkt 7)", () => {
  // Fehler: nach jeder Zahl mit Punkt endete kein Satz mehr („… Grenze 110. Die ILO …“ lief weiter).
  it("endet nach einer Zahl, außer vor einem Monatsnamen", () => {
    expect(ersterSatz("Die obere Grenze ist 110. Die ILO zählt anders.")).toBe("Die obere Grenze ist 110.");
    expect(ersterSatz("Wir rechnen mit dem 1. Juli des Jahres. Danach mehr.")).toBe("Wir rechnen mit dem 1. Juli des Jahres.");
    expect(ersterSatz("Gezählt wird ein Alter bis 110. Die ILO zählt anders.")).toBe("Gezählt wird ein Alter bis 110.");
  });
});

describe("pruefungMalMonat", () => {
  const t = (lieferung: string, name: string, anzahl: number, einstufung: string | null, anhalten = false) => ({
    lieferung,
    name,
    anzahl,
    einstufung,
    anhalten,
  });

  it("Summen je Gruppe und Monat ergeben die Gesamtzahl, ohne Einstufung zählt als noch nicht erklärt", () => {
    const m = pruefungMalMonat([
      t("2025-03", "P13_a", 2, "erklaert-datenproblem", true),
      t("2025-03", "P19_b", 300, null),
      t("2025-04", "P19_b", 310, "nicht-erklaerbar"),
      t("2025-04", "P07_c", 5, "erklaert-plausibel"),
    ]);
    expect(m.gesamt).toBe(4);
    expect(m.jeMonat).toEqual({ "2025-03": 2, "2025-04": 2 });
    expect(m.summen.fehler.gesamt).toBe(1);
    expect(m.summen["kein-fehler"].gesamt).toBe(1);
    expect(m.summen.offen).toEqual({ gesamt: 2, jeMonat: { "2025-03": 1, "2025-04": 1 } });
    expect(m.zeilen.map((z) => z.name)).toEqual(["P07_c", "P13_a", "P19_b"]);
    expect(m.zeilen[1]?.zellen["2025-03"]).toEqual({ anzahl: 2, einstufung: "erklaert-datenproblem", anhalten: true });
  });

  it("zwei Treffer einer Prüfung im Monat: eine Zelle mit Summe und der ernsteren Einstufung, beide zählen", () => {
    const m = pruefungMalMonat([t("2025-05", "P14_x", 1, "erklaert-plausibel"), t("2025-05", "P14_x", 2, "nicht-erklaerbar", true)]);
    expect(m.zeilen[0]?.zellen["2025-05"]).toEqual({ anzahl: 3, einstufung: "nicht-erklaerbar", anhalten: true });
    expect(m.jeMonat["2025-05"]).toBe(2);
    expect(m.gesamt).toBe(2);
  });
});
