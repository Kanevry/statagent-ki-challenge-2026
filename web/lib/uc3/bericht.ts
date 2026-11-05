import { formatZahl } from "@kic/ui/bausteine";
import { literal } from "./beleg";
import { lies, type Lesung, type Sql } from "./db";
import { ladeMassgeblichenLauf, ladeMonatslaeufe, MASSGEBLICH_SQL } from "./laeufe";
import { massnahmeSatz } from "./lauf-detail";
import { monatName, verschieben } from "./monat";
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
  /** Sätze, auf die die umsetzende Regel im maßgeblichen Lauf wirkt; `null` ohne Wirkungszeile. */
  wirkungSaetze: number | null;
  /** Beleg-Abfrage der zugehörigen Rückfrage (meta.rueckfrage.beleg_sql). */
  belegSql: string | null;
}

export interface Rueckfrage {
  nr: string;
  titel: string;
  /** Erster Satz der Frage. */
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
  /** Offene Rückfragen, auf die ein nicht erklärbarer Treffer des Monats wartet (z. B. R8). */
  wartet: string[];
  /** Nicht erklärbare Treffer ohne offene Rückfrage. */
  ohneRueckfrage: number;
}

/** Offene Rückfrage, auf die ein nicht erklärbarer Treffer wartet (Bedingung je Treffer t mit Regel r). */
const OFFENE_RUECKFRAGE = "q.antwort IS NULL AND (q.nr = t.details ->> 'rueckfrage' OR q.regel_name = r.name)";

/** Rückfragen, auf die in jedem Monat etwas wartet; leer, wenn keine alle Monate betrifft. */
export function rueckfragenInAllenMonaten(zeilen: readonly Pick<Berichtszeile, "wartet">[]): string[] {
  if (zeilen.length === 0) return [];
  return zeilen[0].wartet.filter((nr) => zeilen.every((z) => z.wartet.includes(nr)));
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

/** Erster Satz eines Textes; Abkürzungen wie „z. B.“ oder „Nr. 1“ beenden keinen Satz. */
export function ersterSatz(text: string): string {
  const s = text.split(/\s+/).join(" ").trim();
  for (let i = 0; i < s.length; i++) {
    const zeichen = s[i];
    if (zeichen !== "." && zeichen !== "?" && zeichen !== "!") continue;
    const rest = s.slice(i + 1);
    if (rest !== "" && !/^ [A-ZÄÖÜ„]/.test(rest)) continue;
    if (zeichen === "." && ABKUERZUNG.test(s.slice(0, i))) continue;
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
  const umfang = t.umfang?.trim() ? t.umfang.split(/\s+/).join(" ") : `${formatZahl(t.anzahl)} Sätze`;
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
  return MASSGEBLICH_SQL.replace("$1", literal(regelsatz)).replace("SELECT DISTINCT ON (lieferung) *", "SELECT DISTINCT ON (lieferung) id, lieferung");
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
    "  (SELECT count(*) FROM meta.pruefung_treffer p WHERE p.lauf_id = m.id AND p.anzahl > 0) AS auffaelligkeiten,",
    "  (SELECT count(*) FROM meta.pruefung_treffer p WHERE p.lauf_id = m.id AND p.anzahl > 0",
    "     AND coalesce(p.einstufung, 'nicht-erklaerbar') = 'nicht-erklaerbar') AS nicht_erklaerbar,",
    "  EXISTS (SELECT 1 FROM meta.revision v WHERE v.lauf_id = m.id AND v.differenz <> 0) AS revisionsbedarf",
    "FROM massgeblich m ORDER BY m.lieferung;",
  ].join("\n");
}

function massgeblichCte(regelsatz: string): string {
  return [
    "WITH massgeblich AS (",
    massgeblichMitLiteral(regelsatz)
      .split("\n")
      .map((z) => `  ${z}`)
      .join("\n"),
    ")",
  ].join("\n");
}

/** Zahl der Monate mit Bericht und je offener Rückfrage die Zahl der Monate, in denen ein Treffer auf sie wartet. */
export function sqlBerichtsuebersicht(regelsatz = "v1"): string {
  return [
    massgeblichCte(regelsatz),
    "SELECT (SELECT count(*) FROM massgeblich) AS monate_mit_bericht, q.nr AS offene_rueckfrage, q.titel,",
    "       count(DISTINCT m.lieferung) AS monate_wartend",
    "FROM massgeblich m",
    "JOIN meta.pruefung_treffer t ON t.lauf_id = m.id AND t.anzahl > 0 AND coalesce(t.einstufung, 'nicht-erklaerbar') = 'nicht-erklaerbar'",
    "JOIN meta.regel r ON r.id = t.regel_id",
    `JOIN meta.rueckfrage q ON ${OFFENE_RUECKFRAGE}`,
    "GROUP BY q.nr, q.titel ORDER BY monate_wartend DESC, q.nr;",
  ].join("\n");
}

/** Monate mit einem nicht erklärbaren Treffer, an dem keine offene Rückfrage hängt. */
export function sqlOhneRueckfrage(regelsatz = "v1"): string {
  return [
    massgeblichCte(regelsatz),
    "SELECT count(DISTINCT m.lieferung) AS monate_mit_weiterem_offenen",
    "FROM massgeblich m",
    "JOIN meta.pruefung_treffer t ON t.lauf_id = m.id AND t.anzahl > 0 AND coalesce(t.einstufung, 'nicht-erklaerbar') = 'nicht-erklaerbar'",
    "JOIN meta.regel r ON r.id = t.regel_id",
    `WHERE NOT EXISTS (SELECT 1 FROM meta.rueckfrage q WHERE ${OFFENE_RUECKFRAGE});`,
  ].join("\n");
}

export function sqlUeberblick(lauf: Pick<Lauf, "id">): string {
  return [
    "SELECT lieferung, gelesen, gezaehlt, gezaehlt - fortgeschrieben AS gezaehlt_aus_lieferung,",
    "       fortgeschrieben, nicht_gezaehlt, ausgeschlossen, korrigiert",
    `FROM meta.lauf WHERE id = ${literal(lauf.id)};`,
  ].join("\n");
}

export function sqlAuffaelligkeiten(lauf: Pick<Lauf, "id">): string {
  return [
    "SELECT r.name, t.ebene, t.anzahl, t.umfang, coalesce(t.einstufung, 'nicht-erklaerbar') AS einstufung, t.anhalten",
    "FROM meta.pruefung_treffer t JOIN meta.regel r ON r.id = t.regel_id",
    `WHERE t.lauf_id = ${literal(lauf.id)} AND t.anzahl > 0`,
    "ORDER BY r.reihenfolge, r.name;",
  ].join("\n");
}

export function sqlRueckfragen(lauf: Pick<Lauf, "id" | "lieferung">): string {
  const id = literal(lauf.id);
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

export function sqlAnnahmen(lauf: Pick<Lauf, "id" | "lieferung">, quelle: Qualitaetsbericht["annahmenQuelle"]): string {
  if (quelle === "meta.annahme") {
    return [
      "SELECT a.nr, a.regel_name,",
      "  (SELECT sum(w.saetze) FROM meta.regel_wirkung w JOIN meta.regel r ON r.id = w.regel_id",
      `   WHERE w.lauf_id = ${literal(lauf.id)} AND r.name = a.regel_name) AS wirkung_saetze`,
      "FROM meta.annahme a",
      `WHERE a.lieferungen IS NULL OR ${literal(lauf.lieferung)} = ANY (a.lieferungen)`,
      "ORDER BY length(a.nr), a.nr;",
    ].join("\n");
  }
  return [
    "SELECT r.name, r.typ, w.saetze",
    "FROM meta.regel_wirkung w JOIN meta.regel r ON r.id = w.regel_id",
    `WHERE w.lauf_id = ${literal(lauf.id)} AND w.saetze > 0 AND r.typ <> 'pruefung'`,
    "ORDER BY array_position(ARRAY['einlese', 'zuordnung', 'zaehl'], r.typ), r.reihenfolge, r.name;",
  ].join("\n");
}

export function sqlRevision(lauf: Pick<Lauf, "id">): string {
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

/** Wirkung der Regel, die eine Annahme umsetzt, im maßgeblichen Lauf. */
export function sqlAnnahmeWirkung(lauf: Pick<Lauf, "id">, regelName: string): string {
  return [
    "SELECT r.name, r.beschreibung, sum(w.saetze) AS saetze",
    "FROM meta.regel_wirkung w JOIN meta.regel r ON r.id = w.regel_id",
    `WHERE w.lauf_id = ${literal(lauf.id)} AND r.name = ${literal(regelName)}`,
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

/** Übersicht aller Monate mit Revisionsbedarf je Monat. */
export function leseBerichtsliste(regelsatz = "v1"): Promise<Lesung<Berichtszeile[]>> {
  return lies(async (sql) => {
    const [monate, revision, offen] = await Promise.all([
      ladeMonatslaeufe(sql, regelsatz),
      sql<{ lauf_id: number }[]>`
        SELECT DISTINCT v.lauf_id FROM meta.revision v
        WHERE v.differenz <> 0 AND v.lauf_id IN (
          SELECT id FROM meta.lauf WHERE regelsatz = ${regelsatz} AND status IN ('fertig', 'unveraendert'))`,
      sql<{ lauf_id: number; nr: string | null }[]>`
        SELECT t.lauf_id, q.nr
        FROM meta.pruefung_treffer t JOIN meta.regel r ON r.id = t.regel_id
        LEFT JOIN meta.rueckfrage q ON q.antwort IS NULL AND (q.nr = t.details ->> 'rueckfrage' OR q.regel_name = r.name)
        WHERE t.anzahl > 0 AND coalesce(t.einstufung, 'nicht-erklaerbar') = 'nicht-erklaerbar' AND t.lauf_id IN (
          SELECT id FROM meta.lauf WHERE regelsatz = ${regelsatz} AND status IN ('fertig', 'unveraendert'))`,
    ]);
    const mitRevision = new Set(revision.map((z) => Number(z.lauf_id)));
    return monate.map((monat) => {
      const eigene = offen.filter((z) => Number(z.lauf_id) === monat.id);
      const wartet = [...new Set(eigene.map((z) => z.nr).filter((n): n is string => Boolean(n)))].sort(
        (a, b) => a.length - b.length || a.localeCompare(b),
      );
      return {
        monat,
        revisionsbedarf: mitRevision.has(monat.id),
        wartet,
        ohneRueckfrage: eigene.filter((z) => !z.nr).length,
      };
    });
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
  beschreibung: string;
  satz_vorlage: string | null;
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
    const zeilen = await sql<
      {
        nr: string;
        rueckfrage: string | null;
        satz: string;
        begruendung: string;
        regel_name: string | null;
        wirkung_saetze: string | null;
        beleg_sql: string | null;
      }[]
    >`
      SELECT a.nr, a.rueckfrage, a.satz, a.begruendung, a.regel_name,
             (SELECT sum(w.saetze) FROM meta.regel_wirkung w JOIN meta.regel r ON r.id = w.regel_id
              WHERE w.lauf_id = ${lauf.id} AND r.name = a.regel_name) AS wirkung_saetze,
             (SELECT q.beleg_sql FROM meta.rueckfrage q WHERE q.nr = a.rueckfrage) AS beleg_sql
      FROM meta.annahme a
      WHERE a.lieferungen IS NULL OR ${lauf.lieferung} = ANY (a.lieferungen)
      ORDER BY length(a.nr), a.nr`;
    return zeilen.map((z) => ({
      nr: z.nr,
      rueckfrage: z.rueckfrage,
      satz: z.satz,
      begruendung: z.begruendung,
      regelName: z.regel_name,
      wirkungSaetze: z.wirkung_saetze === null ? null : zahl(z.wirkung_saetze),
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
    WHERE w.lauf_id = ${lauf.id} AND w.saetze > 0 AND r.typ <> 'pruefung'
    ORDER BY array_position(ARRAY['einlese', 'zuordnung', 'zaehl'], r.typ), r.reihenfolge, r.name`;
  return zeilen.map((z) => ({
    nr: z.name,
    rueckfrage: z.rueckfrage,
    satz: ersterSatz(z.beschreibung),
    begruendung: ersterSatz(z.begruendung),
    regelName: z.name,
    wirkungSaetze: zahl(z.saetze),
    belegSql: z.beleg_sql,
  }));
}

/** Qualitätsbericht eines Monats; `null`, wenn es für den Monat keinen erfolgreichen Lauf gibt. */
export function leseQualitaetsbericht(lieferung: string, regelsatz = "v1"): Promise<Lesung<Qualitaetsbericht | null>> {
  return lies(async (sql) => {
    const lauf = await ladeMassgeblichenLauf(sql, lieferung, regelsatz);
    if (!lauf) return null;
    const [vormonat, kennzahl, gelaufen, treffer, rueckfragen, annahmeDa, revision] = await Promise.all([
      ladeMassgeblichenLauf(sql, verschieben(lieferung, -1), regelsatz),
      sql<{ korrigiert: string | null }[]>`SELECT korrigiert FROM meta.lauf WHERE id = ${lauf.id}`,
      sql<{ n: string }[]>`SELECT count(*) AS n FROM meta.pruefung_treffer WHERE lauf_id = ${lauf.id}`,
      sql<TrefferZeile[]>`
        SELECT t.ebene, t.anzahl, t.umfang, coalesce(t.einstufung, 'nicht-erklaerbar') AS einstufung, t.massnahme, t.anhalten, t.beleg_sql,
               t.details ->> 'rueckfrage' AS rueckfrage, r.name, r.beschreibung, r.parameter ->> 'satz' AS satz_vorlage
        FROM meta.pruefung_treffer t JOIN meta.regel r ON r.id = t.regel_id
        WHERE t.lauf_id = ${lauf.id} AND t.anzahl > 0
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
    ]);
    const ausTabelle = Boolean(annahmeDa[0]?.da);
    const annahmen = await ladeAnnahmen(sql, lauf, ausTabelle);

    const nrn = new Set(rueckfragen.map((r) => r.nr));
    const verweiseVon = (t: TrefferZeile): string[] => {
      const liste = rueckfragen.filter((r) => r.regel_name === t.name).map((r) => r.nr);
      if (t.rueckfrage && nrn.has(t.rueckfrage) && !liste.includes(t.rueckfrage)) liste.push(t.rueckfrage);
      return liste;
    };
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
        satz: befundSatz(
          { anzahl: zahl(t.anzahl), umfang: t.umfang, vorlage: t.satz_vorlage, beschreibung: t.beschreibung, regel: t.name },
          lieferung,
        ),
        anzahl: zahl(t.anzahl),
        umfang: t.umfang?.trim() || `${formatZahl(zahl(t.anzahl))} Sätze`,
        einstufung: einstufungAus(t.einstufung),
        massnahme:
          massnahmeSatz({
            name: t.name,
            massnahme: t.massnahme,
            einstufung: einstufungAus(t.einstufung).code,
            anhalten: Boolean(t.anhalten),
          }) ?? "",
        massnahmeRoh: t.massnahme,
        anhalten: Boolean(t.anhalten),
        rueckfragen: verweiseVon(t),
        offeneRueckfragen: verweiseVon(t).filter((nr) => rueckfragen.some((r) => r.nr === nr && !r.antwort)),
        belegSql: t.beleg_sql?.trim() || null,
      })),
      rueckfragen: rueckfragen
        .filter((r) => rueckfrageBetrifft({ nr: r.nr, lieferungen: r.lieferungen, regelName: r.regel_name }, lieferung, verweise))
        .map((r) => ({
          nr: r.nr,
          titel: r.titel,
          frage: ersterSatz(r.frage),
          vorschlag: alsSatz(r.vorschlag),
          antwort: r.antwort,
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
            ? `${URSACHEN[z.ursache] ?? z.ursache} (${formatZahl(zahl(z.ursache_anzahl))} Verhältnisse)`
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
