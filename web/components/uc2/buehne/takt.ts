import { akteurName, klartext, themaKurz } from "../namen";
import type { FallZustand, Zug } from "../zustand";

// Die Bühne zeigt immer genau eine Sache: einen Sprecher, den Moderator, das Rundenende oder das Ergebnis. Der Strom
// kommt schneller, als ein Mensch lesen kann (Aufzeichnung: 150 ms je Ereignis), also spielt die Bühne ihn im
// Lesetakt ab. Ereignisse ohne eigene Bühne (Belege, Prüfhinweise, Auswahl) gehen ohne Pause durch.

export type BuehnenArt = "auftakt" | "experte" | "runde" | "zug" | "moderator" | "runde_ende" | "ergebnis" | "abbruch";

/** Wie lange die Bühne bei Tempo 1 auf einem Ereignis steht, in Millisekunden. 0: ohne eigene Bühne. */
export const TAKT_MS: Record<string, number> = {
  start: 1200,
  experte: 4200,
  runde: 1400,
  zug: 3800,
  moderator_notiz: 3600,
  runde_ende: 3200,
};

export function taktMs(art: string | undefined, tempo: number): number {
  const basis = art ? (TAKT_MS[art] ?? 0) : 0;
  return basis === 0 ? 0 : Math.round(basis / Math.max(tempo, 0.25));
}

export interface RohEreignis {
  seq: number;
  art: string;
  akteur?: string | null;
  runde?: number | null;
}

/** Was gerade auf der Bühne steht, abgeleitet aus dem zuletzt gezeigten Ereignis mit eigener Bühne. */
export interface Buehne {
  art: BuehnenArt;
  akteur: string | null;
  runde: number | null;
}

export function buehneAus(gezeigt: readonly RohEreignis[], zustand: FallZustand): Buehne {
  if (zustand.status === "abgebrochen") return { art: "abbruch", akteur: null, runde: null };
  if (zustand.ergebnis) return { art: "ergebnis", akteur: null, runde: null };
  for (let i = gezeigt.length - 1; i >= 0; i--) {
    const e = gezeigt[i]!;
    const runde = e.runde ?? null;
    if (e.art === "zug") return { art: "zug", akteur: e.akteur ?? null, runde };
    if (e.art === "moderator_notiz") return { art: "moderator", akteur: "moderator", runde };
    if (e.art === "runde_ende") return { art: "runde_ende", akteur: null, runde };
    if (e.art === "runde") return { art: "runde", akteur: null, runde };
    if (e.art === "experte") return { art: "experte", akteur: "experte", runde: null };
  }
  return { art: "auftakt", akteur: null, runde: null };
}

const HALTUNG_WORT: Record<number, string> = {
  [-2]: "klar dagegen",
  [-1]: "eher dagegen",
  0: "unentschieden",
  1: "eher dafür",
  2: "klar dafür",
};

export function haltungWort(h: number | undefined): string {
  return h === undefined ? "noch offen" : (HALTUNG_WORT[h] ?? String(h));
}

/** Erster Satz eines Textes, ohne Kennungen. Lange Sätze werden am Wortende gekürzt. */
export function ersterSatz(text: string, max = 180): string {
  const sauber = klartext(text).trim();
  const ende = sauber.search(/[.!?](\s|$)/);
  const satz = ende >= 0 ? sauber.slice(0, ende + 1) : sauber;
  if (satz.length <= max) return satz;
  const schnitt = satz.slice(0, max);
  return `${schnitt.slice(0, Math.max(schnitt.lastIndexOf(" "), max - 20))} …`;
}

/** Ein Thema, über das ein Sprecher gerade spricht, und ob er sich dabei bewegt hat. */
export interface Aussage {
  thema: string;
  titel: string;
  haltung: number;
  vorher: number | null;
  satz: string;
  belegIds: string[];
}

/**
 * Die eine Aussage eines Zugs, die die Bühne groß zeigt: zuerst ein Thema, bei dem sich die Haltung geändert hat,
 * sonst die deutlichste Haltung. Die übrigen Themen stehen nur auf dem Brett.
 */
export function hauptaussage(zug: Zug, davor: Zug | undefined): Aussage | null {
  const themen = Object.values(zug.themen);
  if (themen.length === 0) return null;
  const mitVorher = themen.map((t) => ({ t, vorher: davor?.themen[t.thema]?.haltung ?? null }));
  const bewegt = mitVorher.find(({ t, vorher }) => vorher !== null && vorher !== t.haltung);
  const wahl = bewegt ?? [...mitVorher].sort((a, b) => Math.abs(b.t.haltung) - Math.abs(a.t.haltung))[0]!;
  return {
    thema: wahl.t.thema,
    titel: themaKurz(wahl.t.thema),
    haltung: wahl.t.haltung,
    vorher: wahl.vorher,
    satz: ersterSatz(wahl.t.begruendung.replace(/^Das Thema (stützt|berührt) unser(e)? (Ziel|Grenze): /, "")),
    belegIds: wahl.t.beleg_ids,
  };
}

/** Kurzform für die Sitzreihe und die Punkte auf dem Brett. */
export const KUERZEL: Record<string, string> = {
  aerztekammer: "ÄK",
  finanzministerium: "FM",
  gesetzgeber: "GG",
  gesundheitsministerium: "GM",
  krankenanstalten: "SP",
  laender: "LÄ",
  patienten: "PV",
  pflege: "PF",
  pharma: "PH",
  public_health: "PH",
  sozialpartner: "SO",
  sv: "SV",
  vertragsaerzte: "VÄ",
  wahlaerzte: "WÄ",
};

export function kuerzel(akteur: string): string {
  return KUERZEL[akteur] ?? akteurName(akteur).slice(0, 2).toUpperCase();
}

/** Einordnung eines Themas in Alltagssprache. */
export function kategorieWort(kategorie: string | undefined): string {
  switch (kategorie) {
    case "konsens":
      return "einig";
    case "mehrheit":
      return "Mehrheit dafür";
    case "abgelehnt":
      return "abgelehnt";
    case "offener_konflikt":
      return "strittig";
    default:
      return "noch offen";
  }
}
