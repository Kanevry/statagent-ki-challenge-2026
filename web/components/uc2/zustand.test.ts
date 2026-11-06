import ereignisseJson from "../../app/api/uc2/_fixtures/ereignisse-mock.json";
import { ableiten, bewegungenVon, hatSichBewegt, wende, LEER } from "./zustand";

const alle = ereignisseJson as unknown[];

it("Zustand aus allen 66 Ereignissen: fertig, vier Runden, sechs Teilnehmer, Ergebnis", () => {
  const z = ableiten(alle);
  expect(z.status).toBe("fertig");
  expect(z.letzteSeq).toBe(66);
  expect(z.runden.map((r) => r.nr)).toEqual([1, 2, 3, 4]);
  expect(z.teilnehmer).toHaveLength(6);
  expect(z.unlesbar).toBe(0);
  expect(z.ergebnis?.klassifikation.patientenlenkung?.kategorie).toBe("konsens");
});

it("dasselbe Ereignis zweimal ändert nichts (Wiederverbindung liefert Nummern erneut)", () => {
  const einmal = ableiten(alle.slice(0, 30));
  const doppelt = ableiten([...alle.slice(0, 30), ...alle.slice(10, 30)]);
  expect(doppelt).toEqual(einmal);
});

it("ein kaputtes Ereignis wird gezählt und stürzt nichts ab", () => {
  const z = wende(wende(LEER, { foo: 1 }), { seq: 1, art: "zug", daten: {} });
  expect(z.unlesbar).toBe(2);
  expect(z.status).toBe("laeuft");
});

it("Bewegung: Finanzministerium hat sich in Runde 2 bei Finanzierung bewegt, Ärztekammer nie", () => {
  const z = ableiten(alle);
  expect(hatSichBewegt(z, "finanzministerium")).toBe(true);
  expect(hatSichBewegt(z, "aerztekammer")).toBe(false);
  expect(bewegungenVon(ableiten(alle.slice(0, 35)), "sv")).toEqual([{ thema: "finanzierung", alt: -2, neu: -1, runde: 2 }]);
});

it("das Ereignis abbruch macht aus dem Lauf einen Abbruch und behält die Runden", () => {
  const z = ableiten([
    { ...(alle[0] as object), daten: { ...(alle[0] as { daten: object }).daten, provider: "azure" } },
    ...alle.slice(1, 36),
    { seq: 37, runde: 3, art: "abbruch", akteur: null, daten: { grund: "TimeoutError", meldung: "Zeitüberschreitung nach 30 s" } },
  ]);
  expect(z.status).toBe("abgebrochen");
  expect(z.provider).toBe("azure");
  expect(z.fehler).toEqual({ runde: 3, grund: "TimeoutError", meldung: "Zeitüberschreitung nach 30 s" });
  expect(z.runden.filter((r) => r.ende)).toHaveLength(2);
});

it("ein Ereignis fehler gibt es im Vertrag nicht und ändert den Status nicht", () => {
  const z = ableiten([...alle.slice(0, 5), { seq: 6, runde: 1, art: "fehler", akteur: null, daten: { status: "abgebrochen" } }]);
  expect(z.status).toBe("laeuft");
});

it("event ende mit abgebrochen und letzte_seq setzt auch ohne abbruch-Ereignis den Abbruch", () => {
  const z = ableiten([...alle.slice(0, 5), { seq: 6, art: "ende", daten: { status: "abgebrochen", letzte_seq: 5 } }]);
  expect(z.status).toBe("abgebrochen");
});


it("Moderator-Notiz eines Live-Laufs nennt eigene Themen mit ihrem Titel statt der ID", () => {
  // Fängt rohe Schlüssel wie „digitale_triage“ im Verlauf (Befund UI-Regie 06.11.).
  const mitAuftrag = wende(LEER, {
    seq: 1,
    art: "auftrag",
    akteur: "moderator",
    daten: { ziel: "x", regeln: [], themen: [{ id: "digitale_triage", titel: "Digitale Ersteinschätzung", beschreibung: "" }] },
  });
  const z = wende(mitAuftrag, {
    seq: 2,
    art: "moderator_notiz",
    runde: 1,
    akteur: "moderator",
    daten: { notiz: "Kassenstellen und digitale_triage sind einig.", widersprueche: [], belege_eingefordert: [] },
  });
  expect(z.runden.find((r) => r.nr === 1)?.notiz?.text).toBe("Kassenstellen und Digitale Ersteinschätzung sind einig.");
});
