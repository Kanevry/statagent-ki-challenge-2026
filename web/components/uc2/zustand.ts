import { akteurName, klartext, themaKurz } from "./namen";
import {
  daten as schema,
  ereignisHuelle,
  type Beleg,
  type Ereignis,
  type FallStatus,
  type ZugThema,
} from "./typen";
import type { z } from "zod";

// Aus dem Ereignisstrom wird ein Zustand, den die Oberfläche nur noch zeichnet. Die Funktion `wende` ist rein:
// dasselbe Ereignis, zweimal geliefert (Wiederverbindung), ändert nichts. So bleibt Live und Replay gleich.

type Daten<K extends keyof typeof schema> = z.infer<(typeof schema)[K]>;

export interface Zug {
  runde: number;
  themen: Record<string, ZugThema>;
  zahlen: { wert: number; quelle?: string | null; einheit?: string | null }[];
  bezugAuf: string[];
  modell?: string | null;
}

export interface Notiz {
  runde: number;
  text: string;
  eingefordert: number;
}

export interface Hinweis {
  schluessel: string;
  runde: number | null;
  akteur: string | null;
  text: string;
}

export interface Aenderung {
  runde: number;
  thema: string;
  akteur: string;
  alt: number;
  neu: number;
}

export interface RundeZustand {
  nr: number;
  phase?: string;
  teilnehmer: string[];
  zuege: Record<string, Zug>;
  /** Belege, die ein Akteur vor seinem Zug bekommen hat. */
  belege: Record<string, Beleg[]>;
  notiz?: Notiz;
  /** Nach dem Rundenende: Einordnung je Thema laut Code und die Haltungen aller. */
  ende?: {
    klassifikation: Record<string, string>;
    positionen: Record<string, Record<string, number>>;
    aenderungen: Aenderung[];
  };
}

export type Ergebnis = Daten<"ergebnis">;

/** Abbruch laut Vertrag (#44): Ereignis `abbruch` mit `grund` (Fehlertyp) und `meldung` (höchstens 300 Zeichen). */
export interface FehlerZustand {
  runde: number | null;
  meldung: string | null;
  grund: string | null;
}

export interface FallZustand {
  status: FallStatus;
  frage?: string;
  stichtag?: string;
  maxRunden?: number;
  belegquelle?: string;
  /** Provider des Laufs aus dem Ereignis `start`. */
  provider?: string;
  modelle?: Daten<"start">["modelle"];
  experte?: Daten<"experte">;
  themen: { id: string; titel: string; beschreibung?: string }[];
  auswahl: Daten<"auswahl">["akteure"];
  teilnehmer: string[];
  runden: RundeZustand[];
  /** Akteur-Kennung, "moderator" oder null. */
  sprecher: string | null;
  hinweise: Hinweis[];
  belegIndex: Record<string, Beleg>;
  ergebnis?: Ergebnis;
  fehler?: FehlerZustand;
  letzteSeq: number;
  unlesbar: number;
}

export const LEER: FallZustand = {
  status: "wartet",
  themen: [],
  auswahl: [],
  teilnehmer: [],
  runden: [],
  sprecher: null,
  hinweise: [],
  belegIndex: {},
  letzteSeq: 0,
  unlesbar: 0,
};

function runde(zustand: FallZustand, nr: number | null | undefined): RundeZustand | undefined {
  return zustand.runden.find((r) => r.nr === (nr ?? -1));
}

function mitRunde(zustand: FallZustand, nr: number | null | undefined, aendern: (r: RundeZustand) => RundeZustand): FallZustand {
  if (nr == null) return zustand;
  const vorhanden = runde(zustand, nr);
  const basis: RundeZustand = vorhanden ?? { nr, teilnehmer: zustand.teilnehmer, zuege: {}, belege: {} };
  const neu = aendern(basis);
  const liste = vorhanden ? zustand.runden.map((r) => (r.nr === nr ? neu : r)) : [...zustand.runden, neu];
  return { ...zustand, runden: liste.sort((a, b) => a.nr - b.nr) };
}

function mitHinweis(zustand: FallZustand, hinweis: Hinweis): FallZustand {
  if (zustand.hinweise.some((h) => h.schluessel === hinweis.schluessel)) return zustand;
  return { ...zustand, hinweise: [...zustand.hinweise, hinweis] };
}

const MAX_BELEG_ZEICHEN = 4000;

/** Wendet ein Ereignis an. Nummern bis zur letzten gesehenen werden übergangen (Wiederverbindung liefert sie erneut). */
export function wende(zustand: FallZustand, roh: unknown): FallZustand {
  const huelle = ereignisHuelle.safeParse(roh);
  if (!huelle.success) return { ...zustand, unlesbar: zustand.unlesbar + 1 };
  const e: Ereignis = huelle.data;
  if (e.seq <= zustand.letzteSeq) return zustand;
  const basis: FallZustand = {
    ...zustand,
    letzteSeq: e.seq,
    status: zustand.status === "wartet" ? "laeuft" : zustand.status,
  };
  const lesen = <K extends keyof typeof schema>(art: K): Daten<K> | null => {
    const ergebnis = (schema[art] as unknown as z.ZodType<Daten<K>>).safeParse(e.daten);
    return ergebnis.success ? ergebnis.data : null;
  };
  const unlesbar = () => ({ ...basis, unlesbar: basis.unlesbar + 1 });

  switch (e.art) {
    case "start": {
      const d = lesen("start");
      if (!d) return unlesbar();
      return {
        ...basis,
        frage: d.frage,
        stichtag: d.stichtag,
        maxRunden: d.max_runden,
        belegquelle: d.belegquelle,
        provider: d.provider ?? d.modelle?.akteur?.provider ?? undefined,
        modelle: d.modelle,
      };
    }
    case "experte": {
      const d = lesen("experte");
      return d ? { ...basis, experte: d } : unlesbar();
    }
    case "auftrag": {
      const d = lesen("auftrag");
      return d ? { ...basis, themen: d.themen } : unlesbar();
    }
    case "auswahl": {
      const d = lesen("auswahl");
      if (!d) return unlesbar();
      return { ...basis, auswahl: d.akteure, teilnehmer: d.akteure.filter((a) => a.eingeladen).map((a) => a.akteur) };
    }
    case "runde": {
      const d = lesen("runde");
      if (!d || e.runde == null) return unlesbar();
      const teilnehmer = d.teilnehmer.length > 0 ? d.teilnehmer : basis.teilnehmer;
      const mit = mitRunde({ ...basis, teilnehmer }, e.runde, (r) => ({ ...r, phase: d.phase, teilnehmer }));
      return { ...mit, sprecher: null };
    }
    case "belege": {
      const d = lesen("belege");
      if (!d || !e.akteur) return unlesbar();
      const gekuerzt = d.belege.map((b) => ({ ...b, zitat: b.zitat.slice(0, MAX_BELEG_ZEICHEN) }));
      const index = { ...basis.belegIndex };
      for (const b of gekuerzt) index[b.beleg_id] = b;
      const akteur = e.akteur;
      const mit = mitRunde({ ...basis, belegIndex: index }, e.runde, (r) => ({ ...r, belege: { ...r.belege, [akteur]: gekuerzt } }));
      return { ...mit, sprecher: akteur };
    }
    case "zug": {
      const d = lesen("zug");
      if (!d || !e.akteur || e.runde == null) return unlesbar();
      const akteur = e.akteur;
      const zug: Zug = {
        runde: e.runde,
        themen: Object.fromEntries(d.zug.themen.map((t) => [t.thema, t])),
        zahlen: d.zug.zahlen,
        bezugAuf: d.zug.bezug_auf,
        modell: d.modell,
      };
      const mit = mitRunde(basis, e.runde, (r) => ({ ...r, zuege: { ...r.zuege, [akteur]: zug } }));
      return { ...mit, sprecher: akteur };
    }
    case "moderator_notiz": {
      const d = lesen("moderatorNotiz");
      if (!d || e.runde == null) return unlesbar();
      const nr = e.runde;
      let mit = mitRunde(basis, nr, (r) => ({
        ...r,
        notiz: { runde: nr, text: klartext(d.notiz), eingefordert: d.belege_eingefordert.length },
      }));
      for (const w of d.widersprueche) {
        // Zahlen ohne Beleg meldet der Code zusätzlich als eigenes Ereignis; dieselbe Auffälligkeit nur einmal zeigen.
        if (w.art === "zahl_ohne_beleg") continue;
        mit = mitHinweis(mit, {
          schluessel: `w:${nr}:${w.art}:${w.akteur ?? ""}:${w.thema ?? ""}`,
          runde: nr,
          akteur: w.akteur ?? null,
          text: klartext(`${w.akteur ? `${akteurName(w.akteur)}: ` : ""}${w.beschreibung ?? "Widerspruch gefunden."}`),
        });
      }
      if (d.haltungen_ohne_beleg.length > 0) {
        mit = mitHinweis(mit, {
          schluessel: `ohne-beleg:${nr}`,
          runde: nr,
          akteur: null,
          text: `In Runde ${nr} hat ${d.haltungen_ohne_beleg.length === 1 ? "eine Haltung" : `${d.haltungen_ohne_beleg.length} Haltungen`} keinen Beleg. Sie gilt als Annahme des Modells.`,
        });
      }
      return { ...mit, sprecher: "moderator" };
    }
    case "runde_ende": {
      const d = lesen("rundeEnde");
      if (!d || e.runde == null) return unlesbar();
      const mit = mitRunde(basis, e.runde, (r) => ({
        ...r,
        ende: {
          klassifikation: d.klassifikation,
          positionen: d.zwischenergebnis?.positionen ?? {},
          aenderungen: d.aenderungen,
        },
      }));
      return { ...mit, sprecher: null };
    }
    case "zahl_ohne_beleg": {
      const d = lesen("zahlOhneBeleg");
      if (!d) return unlesbar();
      return mitHinweis(basis, {
        schluessel: `zob:${e.runde}:${e.akteur}:${d.fund}`,
        runde: e.runde ?? null,
        akteur: e.akteur ?? null,
        text: `${akteurName(e.akteur) || "Jemand"} nennt${e.runde ? ` in Runde ${e.runde}` : ""} die Zahl „${klartext(d.fund)}“ ohne Quelle.${d.thema ? ` Es geht um ${themaKurz(d.thema)}.` : ""}`,
      });
    }
    case "ungueltige_ausgabe":
      return mitHinweis(basis, {
        schluessel: `ung:${e.runde}:${e.akteur}`,
        runde: e.runde ?? null,
        akteur: e.akteur ?? null,
        text: `${akteurName(e.akteur) || "Jemand"} hat${e.runde ? ` in Runde ${e.runde}` : ""} keine brauchbare Antwort geliefert. Die Haltung bleibt, wie sie war.`,
      });
    case "beleg_ungueltig":
      return mitHinweis(basis, {
        schluessel: `bu:${e.runde}:${e.akteur}:${e.seq}`,
        runde: e.runde ?? null,
        akteur: e.akteur ?? null,
        text: `${akteurName(e.akteur) || "Jemand"} beruft sich${e.runde ? ` in Runde ${e.runde}` : ""} auf einen Beleg, den es nicht gibt.`,
      });
    case "zitat":
      return mitHinweis(basis, {
        schluessel: `zi:${e.runde}:${e.akteur}:${e.seq}`,
        runde: e.runde ?? null,
        akteur: e.akteur ?? null,
        text: `${akteurName(e.akteur) || "Jemand"} übernimmt${e.runde ? ` in Runde ${e.runde}` : ""} einen langen Satz wörtlich aus einem Beleg.`,
      });
    case "ergebnis": {
      const d = lesen("ergebnis");
      return d ? { ...basis, ergebnis: d, status: "fertig", sprecher: null } : unlesbar();
    }
    case "abbruch": {
      const d = lesen("abbruch");
      return {
        ...basis,
        status: "abgebrochen",
        sprecher: null,
        fehler: {
          runde: e.runde ?? null,
          meldung: d?.meldung ? klartext(d.meldung) : null,
          grund: d?.grund ?? null,
        },
      };
    }
    case "ende": {
      const d = lesen("ende");
      if (d?.status === "abgebrochen") {
        return { ...basis, status: "abgebrochen", sprecher: null, fehler: basis.fehler ?? { runde: null, meldung: null, grund: null } };
      }
      return { ...basis, status: "fertig", sprecher: null };
    }
    default:
      return basis;
  }
}

export function ableiten(ereignisse: readonly unknown[]): FallZustand {
  return ereignisse.reduce<FallZustand>((z, e) => wende(z, e), LEER);
}

/** Die jüngste Runde, in der es schon Züge oder Belege gibt (oder die eben begonnen hat). */
export function aktuelleRunde(z: FallZustand): number {
  return z.runden.at(-1)?.nr ?? 0;
}

/** Letzter und vorletzter Zug eines Akteurs, über alle Runden. */
export function zuegeVon(z: FallZustand, akteur: string): Zug[] {
  return z.runden.flatMap((r) => (r.zuege[akteur] ? [r.zuege[akteur]] : []));
}

export interface Bewegung {
  thema: string;
  alt: number;
  neu: number;
  runde: number;
}

/** Was sich bei einem Akteur zwischen dem vorletzten und dem letzten Zug geändert hat. */
export function bewegungenVon(z: FallZustand, akteur: string): Bewegung[] {
  const zuege = zuegeVon(z, akteur);
  const jetzt = zuege.at(-1);
  const davor = zuege.at(-2);
  if (!jetzt || !davor) return [];
  return Object.values(jetzt.themen).flatMap((t) => {
    const alt = davor.themen[t.thema]?.haltung;
    return alt !== undefined && alt !== t.haltung ? [{ thema: t.thema, alt, neu: t.haltung, runde: jetzt.runde }] : [];
  });
}

/** Hat sich ein Akteur in irgendeiner Runde bewegt? Grundlage für die Marke "bewegt". */
export function hatSichBewegt(z: FallZustand, akteur: string): boolean {
  const zuege = zuegeVon(z, akteur);
  for (let i = 1; i < zuege.length; i++) {
    for (const t of Object.values(zuege[i]!.themen)) {
      const alt = zuege[i - 1]!.themen[t.thema]?.haltung;
      if (alt !== undefined && alt !== t.haltung) return true;
    }
  }
  return false;
}

/** Einordnung je Thema aus den Haltungen der Teilnehmer, für den Zwischenstand vor dem Ergebnis. */
export interface ThemaStand {
  thema: string;
  kategorie: string;
  dafuer: string[];
  dagegen: string[];
  enthalten: string[];
}

export function zwischenstand(z: FallZustand): { runde: number; themen: ThemaStand[] } | null {
  const letzte = [...z.runden].reverse().find((r) => r.ende);
  if (!letzte?.ende) return null;
  const { klassifikation, positionen } = letzte.ende;
  const themen = Object.entries(klassifikation).map(([thema, kategorie]) => {
    const stand: ThemaStand = { thema, kategorie, dafuer: [], dagegen: [], enthalten: [] };
    for (const [akteur, werte] of Object.entries(positionen)) {
      const h = werte[thema] ?? 0;
      (h >= 1 ? stand.dafuer : h <= -1 ? stand.dagegen : stand.enthalten).push(akteur);
    }
    return stand;
  });
  return { runde: letzte.nr, themen };
}

export function endstand(z: FallZustand): ThemaStand[] | null {
  if (!z.ergebnis) return null;
  return Object.entries(z.ergebnis.klassifikation).map(([thema, k]) => ({
    thema,
    kategorie: k.kategorie,
    dafuer: k.zustimmend,
    dagegen: k.ablehnend,
    enthalten: k.enthalten,
  }));
}

/** Haltung eines Akteurs zu einem Thema in jeder Runde, in der er gesprochen hat. */
export function verlaufVon(z: FallZustand, akteur: string, thema: string): { runde: number; haltung: number }[] {
  return zuegeVon(z, akteur).flatMap((zug) => {
    const t = zug.themen[thema];
    return t ? [{ runde: zug.runde, haltung: t.haltung }] : [];
  });
}

/** Die Belege, auf die sich der jüngste Zug eines Akteurs stützt, mit den Themen, die sie stützen. */
export function belegeDesZugs(z: FallZustand, akteur: string): { beleg: Beleg; themen: string[] }[] {
  const zug = zuegeVon(z, akteur).at(-1);
  if (!zug) return [];
  const nachId = new Map<string, string[]>();
  for (const t of Object.values(zug.themen)) {
    for (const id of t.beleg_ids) nachId.set(id, [...(nachId.get(id) ?? []), t.thema]);
  }
  return [...nachId.entries()].flatMap(([id, themen]) => {
    const beleg = z.belegIndex[id];
    return beleg ? [{ beleg, themen }] : [];
  });
}

/**
 * Alle Belege, auf die sich ein Akteur in irgendeiner Runde gestützt hat, mit den Themen und Runden. Belege früherer
 * Runden bleiben so nach späteren Runden erhalten.
 */
export function belegeAllerZuege(z: FallZustand, akteur: string): { beleg: Beleg; themen: string[]; runden: number[] }[] {
  const nachId = new Map<string, { themen: Set<string>; runden: Set<number> }>();
  for (const zug of zuegeVon(z, akteur)) {
    for (const t of Object.values(zug.themen)) {
      for (const id of t.beleg_ids) {
        const eintrag = nachId.get(id) ?? { themen: new Set<string>(), runden: new Set<number>() };
        eintrag.themen.add(t.thema);
        eintrag.runden.add(zug.runde);
        nachId.set(id, eintrag);
      }
    }
  }
  return [...nachId.entries()].flatMap(([id, e]) => {
    const beleg = z.belegIndex[id];
    return beleg ? [{ beleg, themen: [...e.themen], runden: [...e.runden].sort((a, b) => a - b) }] : [];
  });
}

/** Haltung direkt vor der letzten Änderung und die Runde dieser Änderung, `null` wenn sich nichts geändert hat. */
export function letzteAenderung(verlauf: { runde: number; haltung: number }[]): { vorher: number; jetzt: number; runde: number } | null {
  for (let i = verlauf.length - 1; i > 0; i--) {
    if (verlauf[i]!.haltung !== verlauf[i - 1]!.haltung) {
      return { vorher: verlauf[i - 1]!.haltung, jetzt: verlauf[i]!.haltung, runde: verlauf[i]!.runde };
    }
  }
  return null;
}
