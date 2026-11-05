import ereignisseJson from "../../../app/api/uc2/_fixtures/ereignisse-mock.json";
import { ableiten } from "../zustand";
import { buehneAus, ersterSatz, hauptaussage, naechsterIndex, taktMs, wartezeit, type RohEreignis } from "./takt";

const alle = ereignisseJson as unknown as (RohEreignis & Record<string, unknown>)[];

function bis(seq: number) {
  const gezeigt = alle.filter((e) => e.seq <= seq);
  return { gezeigt, zustand: ableiten(gezeigt) };
}

it("die Bühne zeigt immer genau eine Sache: den letzten Sprecher, nicht Belege oder Prüfhinweise", () => {
  // seq 23 ist ein Prüfhinweis (zahl_ohne_beleg) nach dem Zug der Ärztekammer in Runde 2.
  const { gezeigt, zustand } = bis(23);
  expect(buehneAus(gezeigt, zustand)).toEqual({ art: "zug", akteur: "aerztekammer", runde: 2 });
  // seq 24 sind Belege des Finanzministeriums: noch kein Zug, die Ärztekammer steht weiter auf der Bühne.
  const weiter = bis(24);
  expect(buehneAus(weiter.gezeigt, weiter.zustand).akteur).toBe("aerztekammer");
});

it("Moderator, Rundenende und Ergebnis haben je eine eigene Bühne", () => {
  expect(buehneAus(bis(18).gezeigt, bis(18).zustand).art).toBe("moderator");
  expect(buehneAus(bis(19).gezeigt, bis(19).zustand)).toMatchObject({ art: "runde_ende", runde: 1 });
  expect(buehneAus(bis(66).gezeigt, bis(66).zustand).art).toBe("ergebnis");
  expect(buehneAus([], ableiten([])).art).toBe("auftakt");
});

it("die Hauptaussage eines Zugs ist zuerst ein Thema, bei dem sich die Haltung geändert hat", () => {
  const z = bis(25).zustand; // Finanzministerium, Runde 2: Finanzierung +1 → 0
  const r1 = z.runden.find((r) => r.nr === 1)!.zuege.finanzministerium;
  const r2 = z.runden.find((r) => r.nr === 2)!.zuege.finanzministerium!;
  const a = hauptaussage(r2, r1)!;
  expect(a.vorher).not.toBeNull();
  expect(a.vorher).not.toBe(a.haltung);
  // Ohne Vorrunde: die deutlichste Haltung.
  const erste = hauptaussage(r1!, undefined)!;
  expect(Math.abs(erste.haltung)).toBe(Math.max(...Object.values(r1!.themen).map((t) => Math.abs(t.haltung))));
});

it("ein Satz bleibt ein Satz und ohne Kennungen", () => {
  expect(ersterSatz("Wir gehen auf die Position von finanzministerium ein. Zweiter Satz.")).toBe(
    "Wir gehen auf die Position von Finanzministerium ein.",
  );
  expect(ersterSatz("a ".repeat(200), 40).length).toBeLessThanOrEqual(42);
});

it("Takt: Sprecher stehen länger als Rundenbeginn, Belege ohne Pause, doppeltes Tempo halbiert", () => {
  expect(taktMs("zug", 1)).toBeGreaterThan(taktMs("runde", 1));
  expect(taktMs("belege", 1)).toBe(0);
  expect(taktMs("zahl_ohne_beleg", 1)).toBe(0);
  expect(taktMs("zug", 2)).toBe(Math.round(taktMs("zug", 1) / 2));
});

it("Prüfhinweise kommen mit dem Sprecher, zu dem sie gehören (Ereignis 23 mit Zug 22, nicht mit Zug 25)", () => {
  // Nach Ereignis 21 (Belege der Ärztekammer) steht der Index bei 21.
  const bisHier = naechsterIndex(alle, 21);
  expect(alle[bisHier - 1]!.seq).toBe(24); // Zug 22, Hinweis 23 und Belege 24 sind gezeigt, Zug 25 noch nicht.
  const gezeigt = alle.slice(0, bisHier);
  const z = ableiten(gezeigt);
  expect(buehneAus(gezeigt, z).akteur).toBe("aerztekammer");
  expect(z.hinweise.some((h) => h.akteur === "aerztekammer" && h.runde === 2)).toBe(true);
});

it("die Wartezeit hängt am letzten Auftritt, nicht an nachgereichten Belegen", () => {
  expect(wartezeit(alle, 24, 1)).toBe(taktMs("zug", 1));
  expect(wartezeit(alle, 0, 1)).toBe(0);
});

it("die Hauptaussage beginnt mit einem Großbuchstaben, auch nach abgeschnittenem Vorspann", () => {
  const zug = {
    runde: 3,
    themen: {
      kassenstellen: { thema: "kassenstellen", haltung: -1, beleg_ids: [], bedingungen: [], begruendung: "Das Thema berührt unsere Grenze: keine Mehrausgaben ohne Gegenfinanzierung.", zugestaendnis: null },
    },
    zahlen: [],
    bezugAuf: [],
  };
  expect(hauptaussage(zug, undefined)!.satz).toBe("Keine Mehrausgaben ohne Gegenfinanzierung.");
});
