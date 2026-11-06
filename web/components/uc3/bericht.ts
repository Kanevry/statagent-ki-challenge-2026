import { formatZahl } from "@kic/ui/bausteine";
import { literal } from "./beleg";
import { lies, type Lesung, type Sql } from "./db";
import { gruppeAus, type GruppeArt } from "./einstufung-gruppen";
import { ladeMassgeblichenLauf, ladeMonatslaeufe, MASSGEBLICH_SQL, quelleSql } from "./laeufe";
import { fehlendeGruppen, ladeFdCodes, massnahmeSatz, type TrefferDetails } from "./lauf-detail";
import { monatName, verschieben } from "./monat";
import { alltag, alltagOder } from "./sprache";
import type { Lauf, Monatslauf } from "./typen";

/**
 * Qualitätsberichte (#18): Daten der fünf Abschnitte, wie `statagent.berichte.qualitaetsbericht` sie rechnet
 * (Überblick, Auffälligkeiten, Rückfragen, angewendete Regeln mit Annahmen, Revisionsbedarf). Heute direkt aus
 * meta.*; später aus `uc3 berichte --json` und `uc3 annahmen --json`. Die Seiten kennen nur die Typen hier, ein
 * Wechsel der Quelle bleibt in dieser Datei.
 */

// --- Typen (Form wie die JSON-Ausgabe der UC3-CLI, in camelCase) ------------------------------------------

export type EinstufungCode = "erklaert-plausibel" | "erklaert-datenproblem" | "nicht-erklaerbar";
export type Einstufung = { code: EinstufungCode; art: "ok" | "warnung" | "fehler"; wort: string };

export interface Auffaelligkeit {
  nr: number;
  ebene: string;
  regel: string;
  /** Ein Satz in Alltagssprache (Vorlage `parameter.satz` der Prüfregel oder Beschreibung mit Umfang). */
  satz: string;
  anzahl: number;
  umfang: string;
  einstufung: Einstufung;
  massnahme: string;
  anhalten: boolean;
  rueckfragen: string[];
  /** Die davon noch ohne Antwort sind. */
  offeneRueckfragen: string[];
  /** Rohtext aus pruefung_treffer.massnahme, für den Tooltip. */
  massnahmeRoh: string | null;
  belegSql: string | null;
}

export interface Annahme {
  /** F1 bis F10 aus meta.annahme; ohne diese Tabelle der Regelname. */
  nr: string;
  rueckfrage: string | null;
  /** Der Satz ohne „Annahme: “; das Präfix setzt `annahmeSatz`. */
  satz: string;
  begruendung: string;
  regelName: string | null;
  /**
   * Wirkung im maßgeblichen Lauf: bei „regel“ die Sätze aus meta.regel_wirkung der umsetzenden Regel, bei
   * „pruefung“ die Beschäftigungsverhältnisse der einen Prüfung, an der die Annahme hängt. `null`, wenn sich
   * die Zahl nicht eindeutig zuordnen lässt (etwa F7 und F8 teilen sich R5_alter): lieber keine Zahl als eine falsche.
   */
  wirkungSaetze: number | null;
  wirkungQuelle: "regel" | "pruefung" | null;
  /** Regel oder Prüfung, die die Zahl liefert. */
  wirkungRegel: string | null;
  /** Beleg-Abfrage der zugehörigen Rückfrage (meta.rueckfrage.beleg_sql). */
  belegSql: string | null;
}

export interface Rueckfrage {
  nr: string;
  titel: string;
  /** Die ganze Frage, ungekürzt. */
  frage: string;
  vorschlag: string;
  antwort: string | null;
  antwortAm: string | null;
  regelName: string | null;
  offen: boolean;
}

export interface RevisionZeile {
  berichtsmonat: string;
  veroeffentlicht: number;
  aktuell: number;
  differenz: number;
  vorlaeufig: boolean;
  hauptursache: string | null;
}

export interface Ueberblick {
  gelesen: number;
  gezaehlt: number;
  fortgeschrieben: number;
  nichtGezaehlt: number;
  ausgeschlossen: number;
  korrigiert: number;
}

export interface Qualitaetsbericht {
  lauf: Lauf;
  vormonat: Lauf | null;
  ueberblick: Ueberblick;
  pruefungenGelaufen: number;
  auffaelligkeiten: Auffaelligkeit[];
  rueckfragen: Rueckfrage[];
  annahmen: Annahme[];
  /** Woher die Annahmen stammen; bestimmt das SQL im Beleg. */
  annahmenQuelle: "meta.annahme" | "meta.regel";
  revision: RevisionZeile[];
  /** Vormonate, die der Lauf abgeglichen hat (Zeilen „insgesamt“). */
  revisionGeprueft: number;
}

export interface Berichtszeile {
  monat: Monatslauf;
  revisionsbedarf: boolean;
  /**
   * Alle offenen Rückfragen, auf die der Monat wartet: die Fortschreibung (E07), anhaltende Prüfungen und
   * nicht erklärbare Treffer (z. B. März 2025: R4 und R8).
   */
  wartet: string[];
  /** Davon die, an denen die Veröffentlichung hängt (Fortschreibung, anhaltende Prüfung), wie auf der Lauf-Seite. */
  haeltAn: string[];
  /** Prüfungen (Regelname) mit nicht erklärbarem Treffer, zu dem keine offene Rückfrage besteht. */
  ohneRueckfrage: string[];
}

export interface OffeneRueckfrage {
  nr: string;
  titel: string;
  lieferungen: string;
}

export interface Berichtsliste {
  zeilen: Berichtszeile[];
  offeneRueckfragen: OffeneRueckfrage[];
  pruefungen: PruefungMalMonat;
}

export interface PruefungsTreffer {
  lieferung: string;
  name: string;
  anzahl: number;
  einstufung: string | null;
  anhalten: boolean;
}

export interface PruefungMalMonat {
  /** Je Prüfung die Monate mit Fund, nach Regelname sortiert. */
  zeilen: { name: string; zellen: Record<string, { anzahl: number; einstufung: string | null; anhalten: boolean }> }[];
  /** Auffälligkeiten (Treffer), gleiche Zählung wie die Spalte „Auffälligkeiten“ der Monatsliste. */
  jeMonat: Record<string, number>;
  gesamt: number;
  summen: Record<GruppeArt, { jeMonat: Record<string, number>; gesamt: number }>;
}

const RANG: Record<GruppeArt, number> = { offen: 0, fehler: 1, "kein-fehler": 2 };

/** Treffer zu Tabelle und Summen. Hätte eine Prüfung zwei Treffer im Monat: Anzahl addiert, die ernstere Einstufung. */
export function pruefungMalMonat(treffer: readonly PruefungsTreffer[]): PruefungMalMonat {
  const zeilen = new Map<string, PruefungMalMonat["zeilen"][number]>();
  const jeMonat: Record<string, number> = {};
  const summen: PruefungMalMonat["summen"] = {
    fehler: { jeMonat: {}, gesamt: 0 },
    "kein-fehler": { jeMonat: {}, gesamt: 0 },
    offen: { jeMonat: {}, gesamt: 0 },
  };
  for (const t of treffer) {
    const zeile = zeilen.get(t.name) ?? { name: t.name, zellen: {} };
    zeilen.set(t.name, zeile);
    const art = gruppeAus(t.einstufung);
    const alt = zeile.zellen[t.lieferung];
    zeile.zellen[t.lieferung] = alt
      ? {
          anzahl: alt.anzahl + t.anzahl,
          einstufung: RANG[gruppeAus(alt.einstufung)] <= RANG[art] ? alt.einstufung : t.einstufung,
          anhalten: alt.anhalten || t.anhalten,
        }
      : { anzahl: t.anzahl, einstufung: t.einstufung, anhalten: t.anhalten };
    jeMonat[t.lieferung] = (jeMonat[t.lieferung] ?? 0) + 1;
    summen[art].jeMonat[t.lieferung] = (summen[art].jeMonat[t.lieferung] ?? 0) + 1;
    summen[art].gesamt += 1;
  }
  return {
    zeilen: [...zeilen.values()].sort((a, b) => a.name.localeCompare(b.name)),
    jeMonat,
    gesamt: treffer.length,
    summen,
  };
}

/** Offene Rückfrage, an der ein Treffer t mit Regel r hängt. */
const OFFENE_RUECKFRAGE = "q.antwort IS NULL AND (q.nr = t.details ->> 'rueckfrage' OR q.regel_name = r.name)";

/**
 * Offene Rückfragen, die laut `lieferungen` jeden Monat der Liste betreffen und in mindestens einem Monat eine
 * Auffälligkeit offen halten (R8). R1 und R6 gelten auch für alle Monate, halten aber nichts offen.
 */
export function rueckfragenInAllenMonaten(
  zeilen: readonly (Pick<Berichtszeile, "wartet"> & { monat: Pick<Monatslauf, "lieferung"> })[],
  offen: readonly OffeneRueckfrage[],
): OffeneRueckfrage[] {
  if (zeilen.length === 0) return [];
  return offen.filter(
    (q) =>
      zeilen.some((z) => z.wartet.includes(q.nr)) &&
      zeilen.every((z) => rueckfrageBetrifft({ nr: q.nr, lieferungen: q.lieferungen, regelName: null }, z.monat.lieferung)),
  );
}

export interface Regel {
  id: number;
  name: string;
  typ: RegelTyp;
  beschreibung: string;
  begruendung: string;
  grundlage: string;
  gueltigAb: string;
  gueltigBis: string | null;
  freigegebenVon: string | null;
  freigegebenAm: string | null;
}

export type RegelTyp = "einlese" | "zuordnung" | "zaehl" | "pruefung";
export const REGEL_TYPEN: readonly RegelTyp[] = ["einlese", "zuordnung", "zaehl", "pruefung"];

// --- Reine Funktionen -------------------------------------------------------------------------------------

const EINSTUFUNGEN: Record<EinstufungCode, Einstufung> = {
  "erklaert-plausibel": { code: "erklaert-plausibel", art: "ok", wort: "erklärt, plausibel" },
  "erklaert-datenproblem": { code: "erklaert-datenproblem", art: "warnung", wort: "erklärt, Datenproblem" },
  "nicht-erklaerbar": { code: "nicht-erklaerbar", art: "fehler", wort: "nicht erklärbar" },
};

/** Einstufung eines Prüftreffers. Ohne gültigen Code gilt er wie im Generator als nicht erklärbar. */
export function einstufungAus(code: string | null | undefined): Einstufung {
  return EINSTUFUNGEN[(code ?? "") as EinstufungCode] ?? EINSTUFUNGEN["nicht-erklaerbar"];
}

// Abkürzungen, nach denen ein Punkt keinen Satz beendet.
const ABKUERZUNG = /(?:(?:^|[\s(])[A-Za-zÄÖÜäöü]|\bNr|\bca|\bbzw|\binkl|\bvgl|\bAbs|\bbzgl|\busw|\bggf)$/;
// Eine Zahl mit Punkt ist nur vor einem Monatsnamen eine Ordinalzahl („der 1. Juli“); „Grenze 110. Die …“ endet
// dort (Review !77, Punkt 7). Vor einem kleinen Wort endet ohnehin kein Satz.
const ZAHL_AM_ENDE = /(?:^|[\s(])\d+$/;
const MONAT_DANACH = /^ (?:Jänner|Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\b/;
// … oder nach Artikel oder Präposition („mit dem 1. Tag“, „ab 15. Juli“).
// Typische Satzanfänge: davor endet der Satz auch nach „bis 110.“ (Review !77, Folge).
const SATZANFANG = /^ (?:Die|Der|Das|Den|Dem|Des|Ein|Eine|Einen|Wir|Sie|Es|Er|Man|Im|In|Bei|Für|Nach|Mit|Ohne|Dann|Danach|Damit|Dies|Diese|Dieser|Dieses|Auch|Nur|So|Wenn|Weil)\b/;
const ORDINAL_DAVOR = /(?:^|\s)(?:dem|den|der|die|das|am|vom|zum|zur|im|ab|bis|seit|einem|einen|eine)\s+\d+$/i;

/** Erster Satz eines Textes; Abkürzungen wie „z. B.“, „Nr. 1“ oder „der 1. Juli“ beenden keinen Satz. */
export function ersterSatz(text: string): string {
  const s = text.split(/\s+/).join(" ").trim();
  for (let i = 0; i < s.length; i++) {
    const zeichen = s[i];
    if (zeichen !== "." && zeichen !== "?" && zeichen !== "!") continue;
    const rest = s.slice(i + 1);
    if (rest !== "" && !/^ [A-ZÄÖÜ„]/.test(rest)) continue;
    if (zeichen === "." && ABKUERZUNG.test(s.slice(0, i))) continue;
    if (
      zeichen === "." &&
      ZAHL_AM_ENDE.test(s.slice(0, i)) &&
      (MONAT_DANACH.test(rest) || (ORDINAL_DAVOR.test(s.slice(0, i)) && !SATZANFANG.test(rest)))
    ) {
      continue;
    }
    return s.slice(0, i + 1);
  }
  return s;
}

/** Satz mit Großbuchstaben am Anfang und Satzzeichen am Ende. */
export function alsSatz(text: string): string {
  let s = text.split(/\s+/).join(" ").trim();
  if (!s) return "";
  if (s.startsWith("→")) s = `Zugeordnet zu${s.slice(1)}`;
  s = s[0].toUpperCase() + s.slice(1);
  return /[.!?)]$/.test(s) ? s : `${s}.`;
}

/** „Annahme: …“ genau einmal davor, ein Satzende dahinter. */
export function annahmeSatz(satz: string): string {
  const ohne = satz.trim().replace(/^Annahme:\s*/i, "");
  return `Annahme: ${alsSatz(ohne)}`;
}

/**
 * Betrifft eine Rückfrage den Monat? `lieferungen` nennt Monate als „lieferung_JJJJ-MM“; steht „alle“ dabei
 * („lieferung_2024-08 und alle weiteren“, „alle ab lieferung_2024-08“), gilt sie ab dem frühesten genannten
 * Monat. Dazu kommen Rückfragen, auf die ein Prüftreffer des Monats verweist.
 */
export function rueckfrageBetrifft(
  rueckfrage: { nr: string; lieferungen: string; regelName: string | null },
  monat: string,
  verweise: { nrn: ReadonlySet<string>; regeln: ReadonlySet<string> } = { nrn: new Set(), regeln: new Set() },
): boolean {
  if (verweise.nrn.has(rueckfrage.nr)) return true;
  if (rueckfrage.regelName && verweise.regeln.has(rueckfrage.regelName)) return true;
  const monate = [...rueckfrage.lieferungen.matchAll(/(\d{4}-\d{2})/g)].map((t) => t[1]).sort();
  if (monate.includes(monat)) return true;
  return /\balle\b/i.test(rueckfrage.lieferungen) && monate.length > 0 && monate[0] <= monat;
}

/** Satz zu einem Prüftreffer aus der Vorlage `parameter.satz` (Platzhalter {anzahl}, {umfang}, {monat}). */
export function befundSatz(
  t: { anzahl: number; umfang: string | null; vorlage: string | null; beschreibung: string; regel: string },
  monat: string,
): string {
  const umfang = t.umfang?.trim() ? t.umfang.split(/\s+/).join(" ") : `${formatZahl(t.anzahl)} ${t.anzahl === 1 ? "Zeile" : "Zeilen"}`;
  if (t.vorlage) {
    const werte: Record<string, string> = { anzahl: formatZahl(t.anzahl), umfang, monat: monatName(monat) };
    return t.vorlage.replace(/\{(\w+)\}/g, (ganz, name: string) => werte[name] ?? ganz).split(/\s+/).join(" ");
  }
  return alsSatz(`${(t.beschreibung || t.regel).split(/\s+/).join(" ").replace(/\.$/, "")} (${umfang})`);
}

/** Datum als TT.MM.JJJJ in Wiener Zeit. */
export function datum(iso: string | Date | null): string {
  if (!iso) return "";
  return new Intl.DateTimeFormat("de-AT", {
    timeZone: "Europe/Vienna",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(iso));
}

const URSACHEN: Record<string, string> = {
  nachmeldung: "Nachmeldung",
  rueckwirkende_abmeldung: "rückwirkende Abmeldung",
  nicht_mehr_enthalten: "nicht mehr enthalten",
  merkmal_geaendert: "Merkmal geändert",
};

const EBENEN: Record<string, string> = { satz: "Satz", aggregat: "Aggregat", lieferung: "Lieferung" };

function zahl(wert: unknown): number {
  const n = Number(wert ?? 0);
  return Number.isFinite(n) ? n : 0;
}

// --- SQL der Belege (angezeigte Fassung mit Literalen; ausgeführt wird die parametrisierte) ------------

function massgeblichMitLiteral(regelsatz: string): string {
  return massgeblichMit(literal(regelsatz));
}

/** Maßgeblicher Lauf je Monat mit Quelle der Prüftreffer; `ausdruck` ist „$1“ (ausgeführt) oder ein Literal (Beleg). */
export function massgeblichMit(ausdruck: string): string {
  return MASSGEBLICH_SQL.replace("$1", ausdruck).replace(
    "SELECT DISTINCT ON (lieferung) *",
    `SELECT DISTINCT ON (lieferung) id, lieferung,\n  ${quelleSql("meta.lauf").split("\n").join("\n  ")} AS quelle_id`,
  );
}

/** Alle Monate: Auffälligkeiten, davon nicht erklärbar, Revisionsbedarf ja/nein. */
export function sqlBerichtsliste(regelsatz = "v1"): string {
  return [
    "WITH massgeblich AS (",
    massgeblichMitLiteral(regelsatz)
      .split("\n")
      .map((z) => `  ${z}`)
      .join("\n"),
    ")",
    "SELECT m.lieferung,",
    "  (SELECT count(*) FROM meta.pruefung_treffer p WHERE p.lauf_id = m.quelle_id AND p.anzahl > 0) AS auffaelligkeiten,",
    "  (SELECT count(*) FROM meta.pruefung_treffer p WHERE p.lauf_id = m.quelle_id AND p.anzahl > 0",
    "     AND coalesce(p.einstufung, 'nicht-erklaerbar') = 'nicht-erklaerbar') AS nicht_erklaerbar,",
    "  EXISTS (SELECT 1 FROM meta.revision v WHERE v.lauf_id = m.id AND v.differenz <> 0) AS revisionsbedarf",
    "FROM massgeblich m ORDER BY m.lieferung;",
  ].join("\n");
}

export function massgeblichCte(ausdruck: string): string {
  return [
    "WITH massgeblich AS (",
    massgeblichMit(ausdruck)
      .split("\n")
      .map((z) => `  ${z}`)
      .join("\n"),
    ")",
  ].join("\n");
}

/**
 * Je Monat jede offene Rückfrage, auf die er wartet: aus der Fortschreibung (E07, wie die Lauf-Seite), aus einer
 * anhaltenden Prüfung oder aus einem nicht erklärbaren Treffer. `haelt_an` heißt: an ihr hängt die Veröffentlichung.
 * Mit `ausdruck` „$1“ ausgeführt, mit Literal als Beleg gezeigt; so ist der Beleg genau die Abfrage der Seite.
 */
function wartetSql(ausdruck: string): string {
  return [
    massgeblichCte(ausdruck) + ",",
    "wartet AS (",
    "  SELECT m.lieferung, q.nr, true AS haelt_an",
    "  FROM massgeblich m JOIN meta.lauf l ON l.id = m.id",
    "  JOIN meta.rueckfrage q ON q.antwort IS NULL AND q.regel_name LIKE 'E07%' AND strpos(q.lieferungen, m.lieferung) > 0",
    "  WHERE l.fortgeschrieben > 0",
    "  UNION ALL",
    "  SELECT m.lieferung, q.nr, t.anhalten",
    "  FROM massgeblich m",
    "  JOIN meta.pruefung_treffer t ON t.lauf_id = m.quelle_id AND t.anzahl > 0",
    "    AND (t.anhalten OR coalesce(t.einstufung, 'nicht-erklaerbar') = 'nicht-erklaerbar')",
    "  JOIN meta.regel r ON r.id = t.regel_id",
    `  JOIN meta.rueckfrage q ON ${OFFENE_RUECKFRAGE}`,
    ")",
    "SELECT w.lieferung, w.nr, bool_or(w.haelt_an) AS haelt_an, q.titel, q.lieferungen",
    "FROM wartet w JOIN meta.rueckfrage q ON q.nr = w.nr",
    "GROUP BY w.lieferung, w.nr, q.titel, q.lieferungen",
    "ORDER BY w.lieferung, length(w.nr), w.nr;",
  ].join("\n");
}

/** Prüfungen mit nicht erklärbarem Treffer ohne offene Rückfrage: Monate je Prüfung und insgesamt (Zeile „alle“). */
function ohneRueckfrageSql(ausdruck: string): string {
  return [
    massgeblichCte(ausdruck),
    "SELECT coalesce(r.name, 'alle') AS pruefung, count(DISTINCT m.lieferung) AS monate,",
    "       array_agg(DISTINCT m.lieferung ORDER BY m.lieferung) AS lieferungen",
    "FROM massgeblich m",
    "JOIN meta.pruefung_treffer t ON t.lauf_id = m.quelle_id AND t.anzahl > 0 AND coalesce(t.einstufung, 'nicht-erklaerbar') = 'nicht-erklaerbar'",
    "JOIN meta.regel r ON r.id = t.regel_id",
    `WHERE NOT EXISTS (SELECT 1 FROM meta.rueckfrage q WHERE ${OFFENE_RUECKFRAGE})`,
    "GROUP BY ROLLUP (r.name) ORDER BY r.name NULLS FIRST;",
  ].join("\n");
}

/** Offene Rückfragen je Monat (Kopf und Spalte „wartet auf Antwort“ der Übersicht). */
export function sqlBerichtsuebersicht(regelsatz = "v1"): string {
  return wartetSql(literal(regelsatz));
}

/** Beleg zum Kopfsatz der Berichte: je Monat Stand des maßgeblichen Laufs und ob eine Prüfung ihn anhält. */
export function sqlBerichtsstand(regelsatz = "v1"): string {
  return [
    massgeblichCte(literal(regelsatz)),
    "SELECT m.lieferung, l.ergebnis_status,",
    "  EXISTS (SELECT 1 FROM meta.pruefung_treffer p WHERE p.lauf_id = m.quelle_id AND p.anhalten) AS angehalten",
    "FROM massgeblich m JOIN meta.lauf l ON l.id = m.id ORDER BY m.lieferung;",
  ].join("\n");
}

function pruefungMalMonatSql(ausdruck: string): string {
  return [
    massgeblichCte(ausdruck),
    "SELECT m.lieferung, r.name, t.anzahl, t.einstufung, t.anhalten",
    "FROM massgeblich m",
    "JOIN meta.pruefung_treffer t ON t.lauf_id = m.quelle_id AND t.anzahl > 0",
    "JOIN meta.regel r ON r.id = t.regel_id",
    "ORDER BY r.name, m.lieferung;",
  ].join("\n");
}

/** Alle Auffälligkeiten aller maßgeblichen Läufe, eine Zeile je Prüfung und Monat. */
export function sqlPruefungMalMonat(regelsatz = "v1"): string {
  return pruefungMalMonatSql(literal(regelsatz));
}

/** Monate mit einem nicht erklärbaren Treffer, an dem keine offene Rückfrage hängt, je Prüfung und insgesamt. */
export function sqlOhneRueckfrage(regelsatz = "v1"): string {
  return ohneRueckfrageSql(literal(regelsatz));
}

export function sqlUeberblick(lauf: Pick<Lauf, "id" | "quelleId">): string {
  return [
    "SELECT lieferung, gelesen, gezaehlt, gezaehlt - fortgeschrieben AS gezaehlt_aus_lieferung,",
    "       fortgeschrieben, nicht_gezaehlt, ausgeschlossen, korrigiert",
    `FROM meta.lauf WHERE id = ${literal(lauf.id)};`,
  ].join("\n");
}

export function sqlAuffaelligkeiten(lauf: Pick<Lauf, "id" | "quelleId">): string {
  return [
    "SELECT r.name, t.ebene, t.anzahl, t.umfang, coalesce(t.einstufung, 'nicht-erklaerbar') AS einstufung, t.anhalten",
    "FROM meta.pruefung_treffer t JOIN meta.regel r ON r.id = t.regel_id",
    `WHERE t.lauf_id = ${literal(lauf.quelleId)} AND t.anzahl > 0`,
    "ORDER BY r.reihenfolge, r.name;",
  ].join("\n");
}

export function sqlRueckfragen(lauf: Pick<Lauf, "id" | "quelleId" | "lieferung">): string {
  const id = literal(lauf.quelleId);
  return [
    "SELECT q.nr, q.titel, q.lieferungen, q.antwort IS NOT NULL AS beantwortet",
    "FROM meta.rueckfrage q",
    `WHERE strpos(q.lieferungen, ${literal(`lieferung_${lauf.lieferung}`)}) > 0`,
    `   OR (q.lieferungen ~* '\\malle\\M' AND q.ab_lieferung <= ${literal(lauf.lieferung)})`,
    "   OR q.nr IN (SELECT t.details ->> 'rueckfrage' FROM meta.pruefung_treffer t",
    `               WHERE t.lauf_id = ${id} AND t.anzahl > 0)`,
    "   OR q.regel_name IN (SELECT r.name FROM meta.pruefung_treffer t JOIN meta.regel r ON r.id = t.regel_id",
    `                       WHERE t.lauf_id = ${id} AND t.anzahl > 0)`,
    "ORDER BY length(q.nr), q.nr;",
  ].join("\n");
}

export function sqlAnnahmen(lauf: Pick<Lauf, "id" | "quelleId" | "lieferung">, quelle: Qualitaetsbericht["annahmenQuelle"]): string {
  if (quelle === "meta.annahme") return annahmenSql(literal(lauf.lieferung), literal(lauf.quelleId));
  return [
    "SELECT r.name, r.typ, w.saetze",
    "FROM meta.regel_wirkung w JOIN meta.regel r ON r.id = w.regel_id",
    `WHERE w.lauf_id = ${literal(lauf.quelleId)} AND w.saetze > 0 AND r.typ <> 'pruefung'`,
    "ORDER BY array_position(ARRAY['einlese', 'zuordnung', 'zaehl'], r.typ), r.reihenfolge, r.name;",
  ].join("\n");
}

export function sqlRevision(lauf: Pick<Lauf, "id" | "quelleId">): string {
  return [
    "SELECT v.berichtsmonat, v.veroeffentlicht, v.aktuell, v.differenz, u.ursache, u.anzahl AS ursache_anzahl,",
    "       EXISTS (SELECT 1 FROM meta.revision g WHERE g.lauf_id = v.lauf_id AND g.berichtsmonat = v.berichtsmonat",
    "               AND g.gliederung <> 'insgesamt' AND g.differenz <> 0) AS umgeschichtet",
    "FROM meta.revision v",
    "LEFT JOIN LATERAL (SELECT ursache, anzahl FROM meta.revision_ursache u",
    "  WHERE u.lauf_id = v.lauf_id AND u.berichtsmonat = v.berichtsmonat",
    "  ORDER BY abs(anzahl) DESC, ursache LIMIT 1) u ON true",
    `WHERE v.lauf_id = ${literal(lauf.id)} AND v.gliederung = 'insgesamt'`,
    "ORDER BY v.berichtsmonat;",
  ].join("\n");
}

/**
 * Annahmen des Monats mit ihrer Wirkung (`$1` Lieferung, `$2` Quelle der Prüftreffer; als Beleg mit Literalen).
 * Reihenfolge: (1) gehört die Regel nur zu dieser Annahme des Monats und hat eine Wirkungszeile, gilt
 * meta.regel_wirkung; (2) ist die Regel selbst eine Prüfung mit Treffern auf Ebene Satz, gilt deren Anzahl;
 * (3) hängt genau eine Prüfung über die Rückfrage an der Annahme, gilt deren Anzahl (F7 → P04, F8 → P06);
 * sonst keine Zahl.
 */
function annahmenSql(lieferung: string, quelleId: string): string {
  return [
    "WITH a AS (",
    "  SELECT a.*, count(*) OVER (PARTITION BY a.regel_name) AS annahmen_je_regel",
    "  FROM meta.annahme a",
    `  WHERE a.lieferungen IS NULL OR ${lieferung} = ANY (a.lieferungen)`,
    "), p AS (",
    "  SELECT a.nr, r.name, r.name = a.regel_name AS eigene_regel, sum(t.anzahl) AS anzahl",
    "  FROM a",
    `  JOIN meta.pruefung_treffer t ON t.lauf_id = ${quelleId} AND t.anzahl > 0 AND t.ebene = 'satz'`,
    "  JOIN meta.regel r ON r.id = t.regel_id AND (r.name = a.regel_name OR t.details ->> 'rueckfrage' = a.rueckfrage)",
    "  GROUP BY a.nr, r.name, a.regel_name",
    "), e AS (",
    "  SELECT a.*,",
    "    (SELECT sum(w.saetze) FROM meta.regel_wirkung w JOIN meta.regel r ON r.id = w.regel_id",
    `     WHERE w.lauf_id = ${quelleId} AND r.name = a.regel_name) AS regel_saetze,`,
    "    (SELECT p.anzahl FROM p WHERE p.nr = a.nr AND p.eigene_regel) AS eigene_pruefung,",
    "    (SELECT count(*) FROM p WHERE p.nr = a.nr) AS pruefungen,",
    "    (SELECT min(p.name) FROM p WHERE p.nr = a.nr) AS pruefung,",
    "    (SELECT min(p.anzahl) FROM p WHERE p.nr = a.nr) AS pruefung_anzahl,",
    "    EXISTS (SELECT 1 FROM meta.regel r WHERE r.name = a.regel_name AND r.typ = 'pruefung') AS eigene_ist_pruefung",
    "  FROM a",
    ")",
    "SELECT e.nr, e.rueckfrage, e.satz, e.begruendung, e.regel_name,",
    "  CASE WHEN e.annahmen_je_regel = 1 AND e.regel_saetze IS NOT NULL THEN 'regel'",
    "       WHEN e.eigene_pruefung IS NOT NULL OR e.eigene_ist_pruefung OR e.pruefungen = 1 THEN 'pruefung' END AS wirkung_quelle,",
    "  CASE WHEN e.annahmen_je_regel = 1 AND e.regel_saetze IS NOT NULL THEN e.regel_name",
    "       WHEN e.eigene_pruefung IS NOT NULL OR e.eigene_ist_pruefung THEN e.regel_name",
    "       WHEN e.pruefungen = 1 THEN e.pruefung END AS wirkung_regel,",
    "  CASE WHEN e.annahmen_je_regel = 1 AND e.regel_saetze IS NOT NULL THEN e.regel_saetze",
    "       WHEN e.eigene_pruefung IS NOT NULL THEN e.eigene_pruefung",
    "       WHEN e.eigene_ist_pruefung THEN 0",
    "       WHEN e.pruefungen = 1 THEN e.pruefung_anzahl END AS wirkung_saetze,",
    "  (SELECT q.beleg_sql FROM meta.rueckfrage q WHERE q.nr = e.rueckfrage) AS beleg_sql",
    "FROM e ORDER BY length(e.nr), e.nr;",
  ].join("\n");
}

/** Beschäftigungsverhältnisse einer Prüfung auf Ebene Satz im maßgeblichen Lauf (Wirkung einer Annahme). */
export function sqlAnnahmePruefung(lauf: Pick<Lauf, "id" | "quelleId">, pruefung: string): string {
  return [
    "SELECT r.name, sum(t.anzahl) AS beschaeftigungsverhaeltnisse",
    "FROM meta.pruefung_treffer t JOIN meta.regel r ON r.id = t.regel_id",
    `WHERE t.lauf_id = ${literal(lauf.quelleId)} AND r.name = ${literal(pruefung)} AND t.ebene = 'satz'`,
    "GROUP BY r.name;",
  ].join("\n");
}

/** Wirkung der Regel, die eine Annahme umsetzt, im maßgeblichen Lauf. */
export function sqlAnnahmeWirkung(lauf: Pick<Lauf, "id" | "quelleId">, regelName: string): string {
  return [
    "SELECT r.name, r.beschreibung, sum(w.saetze) AS saetze",
    "FROM meta.regel_wirkung w JOIN meta.regel r ON r.id = w.regel_id",
    `WHERE w.lauf_id = ${literal(lauf.quelleId)} AND r.name = ${literal(regelName)}`,
    "GROUP BY r.name, r.beschreibung;",
  ].join("\n");
}

export function sqlRegeln(regelsatz = "v1"): string {
  return [
    "SELECT coalesce(typ, 'alle') AS typ, count(*) AS regeln,",
    "       count(*) FILTER (WHERE freigegeben_von IS NOT NULL) AS freigegeben",
    `FROM meta.regel WHERE regelsatz = ${literal(regelsatz)} AND aktiv`,
    "GROUP BY ROLLUP (typ) ORDER BY typ NULLS FIRST;",
  ].join("\n");
}

// --- Lesen --------------------------------------------------------------------------------------------

/** Übersicht aller Monate mit Revisionsbedarf und offenen Rückfragen je Monat. */
export function leseBerichtsliste(regelsatz = "v1"): Promise<Lesung<Berichtsliste>> {
  return lies(async (sql) => {
    const [monate, revision, wartet, ohne, pruefungen] = await Promise.all([
      ladeMonatslaeufe(sql, regelsatz),
      sql<{ lauf_id: number }[]>`
        SELECT DISTINCT v.lauf_id FROM meta.revision v
        WHERE v.differenz <> 0 AND v.lauf_id IN (
          SELECT id FROM meta.lauf WHERE regelsatz = ${regelsatz} AND status IN ('fertig', 'unveraendert'))`,
      // Feste Abfragetexte aus diesem Modul, der Regelsatz geht als Parameter $1 hinein.
      sql.unsafe<{ lieferung: string; nr: string; haelt_an: boolean; titel: string; lieferungen: string }[]>(
        wartetSql("$1"),
        [regelsatz],
      ),
      sql.unsafe<{ pruefung: string; monate: string; lieferungen: string[] }[]>(ohneRueckfrageSql("$1"), [regelsatz]),
      sql.unsafe<{ lieferung: string; name: string; anzahl: string; einstufung: string | null; anhalten: boolean }[]>(
        pruefungMalMonatSql("$1"),
        [regelsatz],
      ),
    ]);
    const mitRevision = new Set(revision.map((z) => Number(z.lauf_id)));
    const nachNr = (a: string, b: string) => a.length - b.length || a.localeCompare(b);
    const zeilen = monate.map((monat) => {
      const eigene = wartet.filter((z) => z.lieferung === monat.lieferung);
      return {
        monat,
        revisionsbedarf: mitRevision.has(monat.id),
        wartet: [...new Set(eigene.map((z) => z.nr))].sort(nachNr),
        haeltAn: [...new Set(eigene.filter((z) => z.haelt_an).map((z) => z.nr))].sort(nachNr),
        ohneRueckfrage: ohne
          .filter((z) => z.pruefung !== "alle" && (z.lieferungen ?? []).includes(monat.lieferung))
          .map((z) => z.pruefung),
      };
    });
    const offeneRueckfragen = [...new Map(wartet.map((z) => [z.nr, { nr: z.nr, titel: z.titel, lieferungen: z.lieferungen }])).values()].sort(
      (a, b) => nachNr(a.nr, b.nr),
    );
    return {
      zeilen,
      offeneRueckfragen,
      pruefungen: pruefungMalMonat(pruefungen.map((z) => ({ ...z, anzahl: Number(z.anzahl) }))),
    };
  });
}

type TrefferZeile = {
  ebene: string;
  anzahl: string | number;
  umfang: string | null;
  einstufung: string | null;
  massnahme: string | null;
  anhalten: boolean;
  beleg_sql: string | null;
  rueckfrage: string | null;
  name: string;
  art: string | null;
  beschreibung: string;
  satz_vorlage: string | null;
  details: TrefferDetails | null;
};

type RueckfrageZeile = {
  nr: string;
  titel: string;
  lieferungen: string;
  frage: string;
  vorschlag: string;
  regel_name: string | null;
  antwort: string | null;
  antwort_am: Date | string | null;
};

async function ladeAnnahmen(sql: Sql, lauf: Lauf, ausTabelle: boolean): Promise<Annahme[]> {
  if (ausTabelle) {
    // Fester Abfragetext aus diesem Modul, Lieferung und Lauf gehen als Parameter hinein.
    const zeilen = await sql.unsafe<
      {
        nr: string;
        rueckfrage: string | null;
        satz: string;
        begruendung: string;
        regel_name: string | null;
        wirkung_quelle: "regel" | "pruefung" | null;
        wirkung_regel: string | null;
        wirkung_saetze: string | null;
        beleg_sql: string | null;
      }[]
    >(annahmenSql("$1", "$2"), [lauf.lieferung, lauf.quelleId]);
    return zeilen.map((z) => ({
      nr: z.nr,
      rueckfrage: z.rueckfrage,
      satz: alltag(z.satz),
      begruendung: alltag(z.begruendung),
      regelName: z.regel_name,
      wirkungSaetze: z.wirkung_saetze === null ? null : zahl(z.wirkung_saetze),
      wirkungQuelle: z.wirkung_quelle,
      wirkungRegel: z.wirkung_regel,
      belegSql: z.beleg_sql,
    }));
  }
  // Übergang, bis meta.annahme in der Datenbank liegt: Regeln mit Wirkung im Lauf, Satz aus der Beschreibung.
  const zeilen = await sql<
    { name: string; beschreibung: string; begruendung: string; saetze: string; rueckfrage: string | null; beleg_sql: string | null }[]
  >`
    SELECT r.name, r.beschreibung, r.begruendung, w.saetze,
           (SELECT q.nr FROM meta.rueckfrage q WHERE q.regel_name = r.name ORDER BY length(q.nr), q.nr LIMIT 1) AS rueckfrage,
           (SELECT q.beleg_sql FROM meta.rueckfrage q WHERE q.regel_name = r.name ORDER BY length(q.nr), q.nr LIMIT 1) AS beleg_sql
    FROM meta.regel_wirkung w JOIN meta.regel r ON r.id = w.regel_id
    WHERE w.lauf_id = ${lauf.quelleId} AND w.saetze > 0 AND r.typ <> 'pruefung'
    ORDER BY array_position(ARRAY['einlese', 'zuordnung', 'zaehl'], r.typ), r.reihenfolge, r.name`;
  return zeilen.map((z) => ({
    nr: z.name,
    rueckfrage: z.rueckfrage,
    satz: alltag(ersterSatz(z.beschreibung)),
    begruendung: alltag(ersterSatz(z.begruendung)),
    regelName: z.name,
    wirkungSaetze: zahl(z.saetze),
    wirkungQuelle: "regel" as const,
    wirkungRegel: z.name,
    belegSql: z.beleg_sql,
  }));
}

/** Qualitätsbericht eines Monats; `null`, wenn es für den Monat keinen erfolgreichen Lauf gibt. */
export function leseQualitaetsbericht(lieferung: string, regelsatz = "v1"): Promise<Lesung<Qualitaetsbericht | null>> {
  return lies(async (sql) => {
    const lauf = await ladeMassgeblichenLauf(sql, lieferung, regelsatz);
    if (!lauf) return null;
    const [vormonat, kennzahl, gelaufen, treffer, rueckfragen, annahmeDa, revision, fdCodes] = await Promise.all([
      ladeMassgeblichenLauf(sql, verschieben(lieferung, -1), regelsatz),
      sql<{ korrigiert: string | null }[]>`SELECT korrigiert FROM meta.lauf WHERE id = ${lauf.id}`,
      sql<{ n: string }[]>`SELECT count(*) AS n FROM meta.pruefung_treffer WHERE lauf_id = ${lauf.quelleId}`,
      sql<TrefferZeile[]>`
        SELECT t.ebene, t.anzahl, t.umfang, coalesce(t.einstufung, 'nicht-erklaerbar') AS einstufung, t.massnahme, t.anhalten, t.beleg_sql,
               t.details ->> 'rueckfrage' AS rueckfrage, t.details, r.name, r.art, r.beschreibung, r.parameter ->> 'satz' AS satz_vorlage
        FROM meta.pruefung_treffer t JOIN meta.regel r ON r.id = t.regel_id
        WHERE t.lauf_id = ${lauf.quelleId} AND t.anzahl > 0
        ORDER BY r.reihenfolge, r.name, array_position(ARRAY['satz', 'aggregat', 'lieferung'], t.ebene)`,
      sql<RueckfrageZeile[]>`
        SELECT nr, titel, lieferungen, frage, vorschlag, regel_name, antwort, antwort_am
        FROM meta.rueckfrage ORDER BY length(nr), nr`,
      sql<{ da: boolean }[]>`SELECT to_regclass('meta.annahme') IS NOT NULL AS da`,
      sql<
        {
          berichtsmonat: string;
          veroeffentlicht: string;
          aktuell: string;
          differenz: string;
          status_vorher: string;
          ursache: string | null;
          ursache_anzahl: string | null;
          umgeschichtet: boolean;
        }[]
      >`
        SELECT v.berichtsmonat, v.veroeffentlicht, v.aktuell, v.differenz, v.status_vorher,
               u.ursache, u.anzahl AS ursache_anzahl,
               EXISTS (SELECT 1 FROM meta.revision g WHERE g.lauf_id = v.lauf_id AND g.berichtsmonat = v.berichtsmonat
                       AND g.gliederung <> 'insgesamt' AND g.differenz <> 0) AS umgeschichtet
        FROM meta.revision v
        LEFT JOIN LATERAL (
          SELECT ursache, anzahl FROM meta.revision_ursache u
          WHERE u.lauf_id = v.lauf_id AND u.berichtsmonat = v.berichtsmonat
          ORDER BY abs(anzahl) DESC, ursache LIMIT 1
        ) u ON true
        WHERE v.lauf_id = ${lauf.id} AND v.gliederung = 'insgesamt'
        ORDER BY v.berichtsmonat`,
      ladeFdCodes(sql),
    ]);
    const ausTabelle = Boolean(annahmeDa[0]?.da);
    const annahmen = await ladeAnnahmen(sql, lauf, ausTabelle);

    const nrn = new Set(rueckfragen.map((r) => r.nr));
    const verweiseVon = (t: TrefferZeile): string[] => {
      const liste = rueckfragen.filter((r) => r.regel_name === t.name).map((r) => r.nr);
      if (t.rueckfrage && nrn.has(t.rueckfrage) && !liste.includes(t.rueckfrage)) liste.push(t.rueckfrage);
      return liste;
    };
    // Wie die Lauf-Seite (auffaelligkeiten.tsx): Maßnahmen kennen Rückfrage und fehlende Gruppen (Review !77, Punkt 1).
    const gruppen = fehlendeGruppen(treffer.map((t) => ({ art: t.art ?? "", details: t.details })), fdCodes);
    const verweise = {
      nrn: new Set(treffer.map((t) => t.rueckfrage).filter((n): n is string => Boolean(n))),
      regeln: new Set(treffer.map((t) => t.name)),
    };

    return {
      lauf,
      vormonat,
      ueberblick: {
        gelesen: lauf.gelesen,
        gezaehlt: lauf.gezaehlt,
        fortgeschrieben: lauf.fortgeschrieben,
        nichtGezaehlt: lauf.nichtGezaehlt,
        ausgeschlossen: lauf.ausgeschlossen,
        korrigiert: zahl(kennzahl[0]?.korrigiert),
      },
      pruefungenGelaufen: zahl(gelaufen[0]?.n),
      auffaelligkeiten: treffer.map((t, i) => ({
        nr: i + 1,
        ebene: EBENEN[t.ebene] ?? t.ebene,
        regel: t.name,
        satz: alltag(
          befundSatz(
            { anzahl: zahl(t.anzahl), umfang: t.umfang, vorlage: t.satz_vorlage, beschreibung: t.beschreibung, regel: t.name },
            lieferung,
          ),
        ),
        anzahl: zahl(t.anzahl),
        umfang: alltag(t.umfang?.trim() || `${formatZahl(zahl(t.anzahl))} ${zahl(t.anzahl) === 1 ? "Zeile" : "Zeilen"}`),
        einstufung: einstufungAus(t.einstufung),
        massnahme: alltag(
          massnahmeSatz(
            {
              name: t.name,
              massnahme: t.massnahme,
              einstufung: einstufungAus(t.einstufung).code,
              anhalten: Boolean(t.anhalten),
              details: t.details,
              offeneRueckfragen: verweiseVon(t).filter((nr) => rueckfragen.some((r) => r.nr === nr && !r.antwort)),
            },
            { fehlendeGruppen: gruppen },
          ) ?? "",
        ),
        massnahmeRoh: alltagOder(t.massnahme),
        anhalten: Boolean(t.anhalten),
        rueckfragen: verweiseVon(t),
        offeneRueckfragen: verweiseVon(t).filter((nr) => rueckfragen.some((r) => r.nr === nr && !r.antwort)),
        belegSql: t.beleg_sql?.trim() || null,
      })),
      rueckfragen: rueckfragen
        .filter((r) => rueckfrageBetrifft({ nr: r.nr, lieferungen: r.lieferungen, regelName: r.regel_name }, lieferung, verweise))
        .map((r) => ({
          nr: r.nr,
          titel: alltag(r.titel),
          frage: alltag(alsSatz(r.frage)),
          vorschlag: alltag(alsSatz(r.vorschlag)),
          antwort: alltagOder(r.antwort),
          antwortAm: r.antwort_am ? datum(r.antwort_am) : null,
          regelName: r.regel_name,
          offen: !r.antwort,
        })),
      annahmen,
      annahmenQuelle: ausTabelle ? "meta.annahme" : "meta.regel",
      revision: revision
        .filter((z) => zahl(z.differenz) !== 0 || z.umgeschichtet)
        .map((z) => ({
          berichtsmonat: z.berichtsmonat,
          veroeffentlicht: zahl(z.veroeffentlicht),
          aktuell: zahl(z.aktuell),
          differenz: zahl(z.differenz),
          vorlaeufig: z.status_vorher === "vorlaeufig",
          hauptursache:
            zahl(z.differenz) === 0
              ? "Umschichtung zwischen Gruppen, insgesamt unverändert"
              : z.ursache
            ? `${URSACHEN[z.ursache] ?? z.ursache} (${formatZahl(zahl(z.ursache_anzahl))} Beschäftigungsverhältnisse)`
            : null,
        })),
      revisionGeprueft: revision.length,
    };
  });
}

/** Alle aktiven Regeln eines Regelsatzes, nach Typ und Reihenfolge. */
export function leseRegeln(regelsatz = "v1"): Promise<Lesung<Regel[]>> {
  return lies(async (sql) => {
    const zeilen = await sql<
      {
        id: number;
        name: string;
        typ: RegelTyp;
        beschreibung: string;
        begruendung: string;
        grundlage: string;
        gueltig_ab_lieferung: string;
        gueltig_bis_lieferung: string | null;
        freigegeben_von: string | null;
        freigegeben_am: Date | string | null;
      }[]
    >`
      SELECT id, name, typ, beschreibung, begruendung, grundlage, gueltig_ab_lieferung, gueltig_bis_lieferung,
             freigegeben_von, freigegeben_am
      FROM meta.regel WHERE regelsatz = ${regelsatz} AND aktiv
      ORDER BY array_position(ARRAY['einlese', 'zuordnung', 'zaehl', 'pruefung'], typ), reihenfolge, name`;
    return zeilen.map((z) => ({
      id: z.id,
      name: z.name,
      typ: z.typ,
      beschreibung: z.beschreibung,
      begruendung: z.begruendung,
      grundlage: z.grundlage,
      gueltigAb: z.gueltig_ab_lieferung,
      gueltigBis: z.gueltig_bis_lieferung,
      freigegebenVon: z.freigegeben_von,
      freigegebenAm: z.freigegeben_am ? datum(z.freigegeben_am) : null,
    }));
  });
}
