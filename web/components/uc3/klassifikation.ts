import { literal } from "./beleg";
import { lies, type Lesung, type Sql } from "./db";
import { ladeMassgeblichenLauf } from "./laeufe";
import { monatsgrenzen } from "./monat";
import type { Lauf } from "./typen";

/**
 * Klassifikationen für UC3 (#18, Frame XlcSB): Branchenabschnitte ÖNACE 2008 und 2025, Übergänge, Zuordnungsregeln
 * für gelieferte Codes und die kleinen Code-Listen. Nur lesend. Die reinen Funktionen (Vergleich der Abschnitte,
 * Beziehungen aus `stat.uebergang`, Überschrift) sind ohne Datenbank getestet.
 */

/** Letzter Monat mit ÖNACE 2008 und erster mit ÖNACE 2025. */
export const MONAT_ALT = "2024-12";
export const MONAT_NEU = "2025-01";

export interface Abschnitt {
  code: string;
  bezeichnung: string;
}

/** Wie ein Buchstabe 2025 zum Buchstaben 2008 steht. */
export type AbschnittVergleich =
  | { art: "gleich" }
  | { art: "verschoben"; vonCode: string }
  | { art: "neu" };

export interface AbschnittZeile {
  code: string;
  alt: Abschnitt | null;
  neu: Abschnitt | null;
  vergleich: AbschnittVergleich | null;
}

/** Abschnitt „Wirtschaftszweig unbekannt“; er ist kein echter Abschnitt und zählt in keiner Summe der Abschnitte. */
export const UNBEKANNT = "UNB";

/**
 * Vergleicht die Abschnitte 2025 mit 2008 über den Namen: gleicher Name unter gleichem Buchstaben ist „gleich“,
 * gleicher Name unter anderem Buchstaben „verschoben“, ein Name, den es 2008 nicht gab, „neu“ zugeschnitten.
 * Eine Zeile je Buchstabe, sortiert, damit sichtbar wird, dass derselbe Buchstabe 2025 etwas anderes heißen kann.
 */
export function vergleicheAbschnitte(alt: readonly Abschnitt[], neu: readonly Abschnitt[]): AbschnittZeile[] {
  const altNachName = new Map(alt.map((a) => [a.bezeichnung, a.code]));
  const altNachCode = new Map(alt.map((a) => [a.code, a]));
  const neuNachCode = new Map(neu.map((n) => [n.code, n]));
  const codes = [...new Set([...altNachCode.keys(), ...neuNachCode.keys()])].sort(abschnittReihenfolge);
  return codes.map((code) => {
    const n = neuNachCode.get(code) ?? null;
    let vergleich: AbschnittVergleich | null = null;
    if (n) {
      const vonCode = altNachName.get(n.bezeichnung);
      vergleich = vonCode === undefined ? { art: "neu" } : vonCode === code ? { art: "gleich" } : { art: "verschoben", vonCode };
    }
    return { code, alt: altNachCode.get(code) ?? null, neu: n, vergleich };
  });
}

/** Buchstaben alphabetisch, „unbekannt“ am Ende. */
function abschnittReihenfolge(a: string, b: string): number {
  if (a === UNBEKANNT) return b === UNBEKANNT ? 0 : 1;
  if (b === UNBEKANNT) return -1;
  return a.localeCompare(b, "de");
}

export interface Wechselzahlen {
  abschnitteAlt: number;
  abschnitteNeu: number;
  gleich: number;
  verschoben: number;
  neu: number;
}

/** Zahlen für Überschrift und Einleitung, ohne „Wirtschaftszweig unbekannt“ (wie `sqlWechselzahlen`). */
export function wechselzahlen(zeilen: readonly AbschnittZeile[]): Wechselzahlen {
  const echt = zeilen.filter((z) => z.code !== UNBEKANNT);
  const zaehle = (art: AbschnittVergleich["art"]) => echt.filter((z) => z.vergleich?.art === art).length;
  return {
    abschnitteAlt: echt.filter((z) => z.alt).length,
    abschnitteNeu: echt.filter((z) => z.neu).length,
    gleich: zaehle("gleich"),
    verschoben: zaehle("verschoben"),
    neu: zaehle("neu"),
  };
}

/** Hauptsatz der Seite: ein vollständiger Satz mit den echten Zahlen. */
export function wechselSatz(z: Wechselzahlen): string {
  const anzahl = z.abschnitteNeu === z.abschnitteAlt ? `${z.abschnitteNeu} Abschnitten wie bisher` : `${z.abschnitteNeu} statt ${z.abschnitteAlt} Abschnitten`;
  return `Ab Jänner 2025 zählen wir Branchen nach ÖNACE 2025 mit ${anzahl}; nur ${z.gleich} behalten Buchstabe und Namen.`;
}

/** SQL, das die Zahlen von `wechselzahlen` liefert (Vergleich über den Namen, ohne UNB). */
export function sqlWechselzahlen(): string {
  return [
    "WITH a AS (SELECT code, bezeichnung FROM stat.klass_oenace",
    "           WHERE version = '2008' AND ebene = 1 AND code <> 'UNB'),",
    "     n AS (SELECT code, bezeichnung FROM stat.klass_oenace",
    "           WHERE version = '2025' AND ebene = 1 AND code <> 'UNB')",
    "SELECT (SELECT count(*) FROM a) AS abschnitte_2008,",
    "       (SELECT count(*) FROM n) AS abschnitte_2025,",
    "       count(*) FILTER (WHERE a.code = n.code) AS gleicher_buchstabe_und_name,",
    "       count(*) FILTER (WHERE a.code <> n.code) AS gleicher_name_anderer_buchstabe,",
    "       count(*) FILTER (WHERE a.code IS NULL) AS neu_zugeschnitten",
    "FROM n LEFT JOIN a ON a.bezeichnung = n.bezeichnung;",
  ].join("\n");
}

/** SQL der Abschnittsliste beider Fassungen, wie die Tabelle sie zeigt. */
export function sqlAbschnitte(): string {
  return [
    "SELECT version, code, bezeichnung FROM stat.klass_oenace",
    "WHERE ebene = 1 AND version IN ('2008', '2025')",
    "ORDER BY code, version;",
  ].join("\n");
}

// ---------------------------------------------------------------------------------------------------------------
// Übergänge aus stat.uebergang

export interface Uebergang {
  versionAlt: string;
  codeAlt: string;
  versionNeu: string;
  codeNeu: string;
}

export type UebergangWort = "gleich" | "aufgeteilt" | "zusammengelegt";

export interface UebergangAlt {
  codeAlt: string;
  ziele: string[];
  wort: UebergangWort;
}

/**
 * Wort für jeden alten Code, aus der Struktur der Übergänge statt aus dem Feld `beziehung`: geht ein alter Code an
 * mehrere neue, ist er „aufgeteilt“; teilt er sein Ziel mit anderen alten Codes, ist er „zusammengelegt“; sonst
 * „gleich“. Aufgeteilt hat Vorrang, weil ein Teil der Sätze dann woanders landen müsste.
 */
export function uebergangsWorte(zeilen: readonly Uebergang[]): UebergangAlt[] {
  const ziele = new Map<string, Set<string>>();
  const quellen = new Map<string, Set<string>>();
  for (const z of zeilen) {
    (ziele.get(z.codeAlt) ?? ziele.set(z.codeAlt, new Set()).get(z.codeAlt))?.add(z.codeNeu);
    (quellen.get(z.codeNeu) ?? quellen.set(z.codeNeu, new Set()).get(z.codeNeu))?.add(z.codeAlt);
  }
  return [...ziele.entries()]
    .sort(([a], [b]) => a.localeCompare(b, "de"))
    .map(([codeAlt, zielMenge]) => {
      const liste = [...zielMenge].sort((a, b) => a.localeCompare(b, "de"));
      const wort: UebergangWort =
        liste.length > 1
          ? "aufgeteilt"
          : liste.some((ziel) => (quellen.get(ziel)?.size ?? 0) > 1)
            ? "zusammengelegt"
            : "gleich";
      return { codeAlt, ziele: liste, wort };
    });
}

/** Anzahl alter Codes je Wort. */
export function zaehleUebergangsWorte(worte: readonly UebergangAlt[]): Record<UebergangWort, number> {
  const zahl: Record<UebergangWort, number> = { gleich: 0, aufgeteilt: 0, zusammengelegt: 0 };
  for (const w of worte) zahl[w.wort] += 1;
  return zahl;
}

export function sqlUebergaenge(): string {
  return [
    "SELECT version_alt, code_alt, version_neu, code_neu, beziehung, quelle",
    "FROM stat.uebergang WHERE klassifikation = 'oenace'",
    "ORDER BY version_alt, version_neu, code_alt, code_neu;",
  ].join("\n");
}

// ---------------------------------------------------------------------------------------------------------------
// Verhältnisse je Abschnitt am Stichtag Dez 2024 und Jän 2025

export interface AbschnittBestand {
  version: string;
  code: string;
  wert: number;
}

function stichtagsFilter(lauf: Pick<Lauf, "lieferung" | "regelstand">): string {
  const { von, bis } = monatsgrenzen(lauf.lieferung);
  return `(s.regelstand = ${literal(lauf.regelstand)} AND s.zeitraum_bis BETWEEN ${literal(von)} AND ${literal(bis)})`;
}

/** SQL der Verhältnisse je Abschnitt in beiden Monaten, jeweils aus dem maßgeblichen Lauf. */
export function sqlAbschnittBestand(
  alt: Pick<Lauf, "lieferung" | "regelstand" | "regelsatz">,
  neu: Pick<Lauf, "lieferung" | "regelstand" | "regelsatz">,
): string {
  return [
    "SELECT s.oenace_version, s.oenace, sum(s.wert) AS beschaeftigungsverhaeltnisse",
    "FROM stat.stat_beschaeftigte s",
    `WHERE s.regelsatz = ${literal(alt.regelsatz)}`,
    "  AND s.zeitraum_art = 'Stichtag' AND s.variable = 'Beschaeftigungsverhaeltnisse'",
    `  AND (${stichtagsFilter(alt)}`,
    `    OR ${stichtagsFilter(neu)})`,
    "GROUP BY 1, 2 ORDER BY 2, 1;",
  ].join("\n");
}

// ---------------------------------------------------------------------------------------------------------------
// Zuordnungsregeln für gelieferte Codes (stat.quellzuordnung + meta.regel)

export interface Zuordnung {
  merkmal: string;
  version: string;
  geliefert: string;
  code: string;
}

export interface Zuordnungsregel {
  id: number;
  name: string;
  beschreibung: string;
  freigegebenVon: string | null;
  freigegebenAm: Date | null;
  zuordnungen: Zuordnung[];
}

export function sqlZuordnungsregel(id: number, regelsatz = "v1"): string {
  return [
    "SELECT r.name, r.freigegeben_von, r.freigegeben_am,",
    "       count(DISTINCT q.geliefert) AS gelieferte_codes,",
    "       string_agg(DISTINCT q.merkmal || ' ' || q.code, ', ') AS ziele,",
    "       string_agg(DISTINCT q.version, ', ') AS fassungen",
    "FROM stat.quellzuordnung q JOIN meta.regel r ON r.id = q.regel_id",
    `WHERE q.regelsatz = ${literal(regelsatz)} AND q.regel_id = ${literal(id)}`,
    "GROUP BY r.name, r.freigegeben_von, r.freigegeben_am;",
  ].join("\n");
}

/** Gelieferte Codes einer Regel ohne Doppel über die ÖNACE-Fassungen (DA kommt 2008 und 2025 vor). */
export function gelieferteCodes(zuordnungen: readonly Zuordnung[], merkmal: string): string[] {
  return [...new Set(zuordnungen.filter((z) => z.merkmal === merkmal).map((z) => z.geliefert))].sort((a, b) =>
    a.localeCompare(b, "de"),
  );
}

// ---------------------------------------------------------------------------------------------------------------
// Kleine Listen

export interface Qualifikation {
  code: string;
  bezeichnung: string;
  kategorie: string;
  freierDienstvertrag: boolean | null;
}

export interface Altersgruppe {
  gruppe: string;
  von: number;
  bis: number;
}

export const SQL_BUNDESLAENDER = [
  "SELECT code, bezeichnung FROM stat.klass_region",
  "WHERE ebene = 'bundesland' ORDER BY code;",
].join("\n");

export const SQL_QUALIFIKATIONEN = [
  "SELECT code, bezeichnung, beschaeftigungskategorie, freier_dienstvertrag",
  "FROM stat.klass_qualifikation ORDER BY beschaeftigungskategorie, code;",
].join("\n");

export const SQL_ALTERSGRUPPEN = [
  "SELECT berichtsgruppe, min(code) AS von, max(code) AS bis",
  "FROM stat.klass_alter GROUP BY berichtsgruppe ORDER BY min(code);",
].join("\n");

export const SQL_GESCHLECHT = "SELECT code, bezeichnung FROM stat.klass_geschlecht ORDER BY code;";

// ---------------------------------------------------------------------------------------------------------------
// Laden

export interface Klassifikationsdaten {
  abschnitte: AbschnittZeile[];
  uebergaenge: Uebergang[];
  regeln: Zuordnungsregel[];
  bestand: { alt: Lauf; neu: Lauf; werte: AbschnittBestand[] } | null;
  bundeslaender: Abschnitt[];
  geschlechter: Abschnitt[];
  qualifikationen: Qualifikation[];
  altersgruppen: Altersgruppe[];
  kategorieStand: KategorieStand | null;
}

const zahl = (wert: unknown): number => Number(wert ?? 0);

async function ladeBestand(sql: Sql): Promise<Klassifikationsdaten["bestand"]> {
  const [alt, neu] = await Promise.all([ladeMassgeblichenLauf(sql, MONAT_ALT), ladeMassgeblichenLauf(sql, MONAT_NEU)]);
  if (!alt || !neu) return null;
  const a = monatsgrenzen(alt.lieferung);
  const n = monatsgrenzen(neu.lieferung);
  const zeilen = await sql<{ oenace_version: string; oenace: string; wert: string }[]>`
    SELECT s.oenace_version, s.oenace, sum(s.wert) AS wert
    FROM stat.stat_beschaeftigte s
    WHERE s.regelsatz = ${alt.regelsatz}
      AND s.zeitraum_art = 'Stichtag' AND s.variable = 'Beschaeftigungsverhaeltnisse'
      AND ((s.regelstand = ${alt.regelstand} AND s.zeitraum_bis BETWEEN ${a.von} AND ${a.bis})
        OR (s.regelstand = ${neu.regelstand} AND s.zeitraum_bis BETWEEN ${n.von} AND ${n.bis}))
    GROUP BY 1, 2`;
  return { alt, neu, werte: zeilen.map((z) => ({ version: z.oenace_version, code: z.oenace, wert: zahl(z.wert) })) };
}

async function ladeRegeln(sql: Sql, regelsatz: string): Promise<Zuordnungsregel[]> {
  const zeilen = await sql<
    {
      id: number;
      name: string;
      beschreibung: string;
      freigegeben_von: string | null;
      freigegeben_am: Date | null;
      merkmal: string;
      version: string;
      geliefert: string;
      code: string;
    }[]
  >`
    SELECT r.id, r.name, r.beschreibung, r.freigegeben_von, r.freigegeben_am, q.merkmal, q.version, q.geliefert, q.code
    FROM stat.quellzuordnung q JOIN meta.regel r ON r.id = q.regel_id
    WHERE q.regelsatz = ${regelsatz}
    ORDER BY r.id, q.merkmal, q.version, q.geliefert`;
  const regeln = new Map<number, Zuordnungsregel>();
  for (const z of zeilen) {
    const regel =
      regeln.get(z.id) ??
      regeln
        .set(z.id, {
          id: z.id,
          name: z.name,
          beschreibung: z.beschreibung,
          freigegebenVon: z.freigegeben_von,
          freigegebenAm: z.freigegeben_am,
          zuordnungen: [],
        })
        .get(z.id);
    regel?.zuordnungen.push({ merkmal: z.merkmal, version: z.version, geliefert: z.geliefert, code: z.code });
  }
  return [...regeln.values()];
}

/** Alles für die Seite in einem `lies()`-Aufruf mit parallelen Abfragen. */
export function leseKlassifikationen(regelsatz = "v1"): Promise<Lesung<Klassifikationsdaten>> {
  return lies(async (sql) => {
    const [oenace, uebergaenge, regeln, bestand, bundeslaender, geschlechter, qualifikationen, altersgruppen, kategorieStand] =
      await Promise.all([
        sql<{ version: string; code: string; bezeichnung: string }[]>`
          SELECT version, code, bezeichnung FROM stat.klass_oenace
          WHERE ebene = 1 AND version IN ('2008', '2025')`,
        sql<{ version_alt: string; code_alt: string; version_neu: string; code_neu: string }[]>`
          SELECT version_alt, code_alt, version_neu, code_neu FROM stat.uebergang
          WHERE klassifikation = 'oenace' ORDER BY version_alt, version_neu, code_alt, code_neu`,
        ladeRegeln(sql, regelsatz),
        ladeBestand(sql),
        sql<Abschnitt[]>`SELECT code, bezeichnung FROM stat.klass_region WHERE ebene = 'bundesland' ORDER BY code`,
        sql<Abschnitt[]>`SELECT code, bezeichnung FROM stat.klass_geschlecht ORDER BY code`,
        sql<{ code: string; bezeichnung: string; beschaeftigungskategorie: string; freier_dienstvertrag: boolean | null }[]>`
          SELECT code, bezeichnung, beschaeftigungskategorie, freier_dienstvertrag
          FROM stat.klass_qualifikation ORDER BY beschaeftigungskategorie, code`,
        sql<{ berichtsgruppe: string; von: number; bis: number }[]>`
          SELECT berichtsgruppe, min(code) AS von, max(code) AS bis
          FROM stat.klass_alter GROUP BY berichtsgruppe ORDER BY min(code)`,
        ladeKategorieStand(sql, regelsatz),
      ]);
    const nach = (version: string) =>
      oenace.filter((o) => o.version === version).map(({ code, bezeichnung }) => ({ code, bezeichnung }));
    return {
      abschnitte: vergleicheAbschnitte(nach("2008"), nach("2025")),
      uebergaenge: uebergaenge.map((u) => ({
        versionAlt: u.version_alt,
        codeAlt: u.code_alt,
        versionNeu: u.version_neu,
        codeNeu: u.code_neu,
      })),
      regeln,
      bestand,
      bundeslaender: bundeslaender.map(({ code, bezeichnung }) => ({ code, bezeichnung })),
      geschlechter: geschlechter.map(({ code, bezeichnung }) => ({ code, bezeichnung })),
      qualifikationen: qualifikationen.map((q) => ({
        code: q.code,
        bezeichnung: q.bezeichnung,
        kategorie: q.beschaeftigungskategorie,
        freierDienstvertrag: q.freier_dienstvertrag,
      })),
      altersgruppen: altersgruppen.map((g) => ({ gruppe: g.berichtsgruppe, von: zahl(g.von), bis: zahl(g.bis) })),
      kategorieStand,
    };
  });
}

// ---------------------------------------------------------------------------------------------------------------
// Sätze zu den Zuordnungsregeln

const MERKMAL_WORT: Record<string, string> = {
  bundesland: "Bundesland",
  oenace: "Branche",
  geschlecht: "Geschlecht",
  qualifikation: "Qualifikation",
};
const MERKMAL_REIHE = ["bundesland", "oenace", "geschlecht", "qualifikation"];

/** „Bundesland 0, Branche UNB“: Ziel je Merkmal, ohne Doppel über ÖNACE-Fassungen. */
function zieleJeMerkmal(zuordnungen: readonly Zuordnung[]): string {
  const ziel = new Map<string, string>();
  for (const z of zuordnungen) ziel.set(z.merkmal, z.code);
  const teile = MERKMAL_REIHE.filter((m) => ziel.has(m)).map((m) => `${MERKMAL_WORT[m]} ${ziel.get(m)}`);
  return teile.length < 2 ? (teile[0] ?? "") : `${teile.slice(0, -1).join(", ")} und ${teile.at(-1)}`;
}

/**
 * Ein Satz in Alltagssprache je Zuordnungsregel, gebildet aus ihren Zeilen in `stat.quellzuordnung`: leere Felder,
 * unbekannte Werte oder eine Gruppe gelieferter Codes, die auf einen Code gehen. Sonst die Beschreibung der Regel.
 */
export function regelSatz(regel: Zuordnungsregel, bezeichnung: (code: string) => string | undefined): string {
  const geliefert = new Set(regel.zuordnungen.map((z) => z.geliefert));
  if (geliefert.size === 1 && geliefert.has("<leer>")) {
    return `Ist ein Feld leer, zählen wir die Zeile unter unbekannt: ${zieleJeMerkmal(regel.zuordnungen)}.`;
  }
  if (geliefert.size === 1 && geliefert.has("<sonst>")) {
    return `Kennt keine Liste den gelieferten Wert, zählen wir die Zeile ebenfalls unter unbekannt (${zieleJeMerkmal(regel.zuordnungen)}) und melden ihn als Auffälligkeit.`;
  }
  const ziele = new Set(regel.zuordnungen.map((z) => z.code));
  const merkmale = new Set(regel.zuordnungen.map((z) => z.merkmal));
  const [ziel] = [...ziele];
  const [merkmal] = [...merkmale];
  if (ziele.size === 1 && merkmale.size === 1 && ziel && merkmal) {
    const codes = gelieferteCodes(regel.zuordnungen, merkmal);
    const name = bezeichnung(ziel);
    const spanne = codes.length > 2 ? `${codes[0]} bis ${codes.at(-1)}` : codes.join(" und ");
    return `Die alten Codes ${spanne} (${codes.length} Codes) zählen wir unter ${ziel}${name ? ` „${name}“` : ""}.`;
  }
  return regel.beschreibung;
}

/** Anzahl Qualifikationen und Beschäftigungskategorien, ohne „unbekannt“. */
export function qualifikationsZahlen(liste: readonly Qualifikation[]): { qualifikationen: number; kategorien: number } {
  const bekannt = liste.filter((q) => q.code !== UNBEKANNT);
  return { qualifikationen: bekannt.length, kategorien: new Set(bekannt.map((q) => q.kategorie)).size };
}

export const SQL_QUALIFIKATION_ZAHLEN = [
  "SELECT count(*) AS qualifikationen,",
  "       count(DISTINCT beschaeftigungskategorie) AS kategorien",
  "FROM stat.klass_qualifikation WHERE code <> 'UNB';",
].join("\n");

// ---------------------------------------------------------------------------------------------------------------
// Zählregel der Beschäftigungskategorie: Stand je Regelsatz und der Auftrag, der sie ändert (meta.regel, meta.vorschlag)

export interface KategorieAuftrag {
  vorschlagId: number;
  /** Teil der Anweisung vor dem ersten Doppelpunkt, etwa „Auftrag 1, Dienstvertrag und freier Dienstvertrag zusammen“. */
  titel: string;
  status: "offen" | "freigegeben" | "abgelehnt";
  regelsatzZiel: string;
  /** Spalte, nach der der Ziel-Regelsatz zählt (aktive Regel, sonst laut Vorschlag). */
  zielSpalte: string | null;
  /** Freigabe oder Ablehnung: Name und Zeitpunkt (ISO). */
  von: string | null;
  am: string | null;
}

export interface KategorieStand {
  regelsatz: string;
  regelId: number;
  regelName: string;
  /** Spalte von stat.klass_qualifikation, nach der gezählt wird: „code“ (einzeln) oder „beschaeftigungskategorie“. */
  spalte: string;
  auftrag: KategorieAuftrag | null;
}

/** Abfrage hinter der Zählregel der Qualifikation in einem Regelsatz (für den Beleg). */
export function sqlKategorieRegel(regelsatz: string): string {
  return [
    "SELECT id, regelsatz, name, parameter->>'qualifikation' AS spalte, freigegeben_von, freigegeben_am",
    "FROM meta.regel",
    `WHERE regelsatz = ${literal(regelsatz)} AND aktiv AND parameter ? 'qualifikation'`,
    "ORDER BY id DESC LIMIT 1;",
  ].join("\n");
}

/** Abfrage hinter dem Auftrag, der diese Regel ändert, mit Freigabe in Wiener Zeit (für den Beleg). */
export function sqlKategorieAuftrag(stand: Pick<KategorieStand, "regelsatz" | "regelName" | "regelId">): string {
  return [
    "SELECT v.id, split_part(v.anweisung, ':', 1) AS auftrag, v.status, v.regelsatz_ziel,",
    "       v.freigegeben_von, v.freigegeben_am AT TIME ZONE 'Europe/Vienna' AS freigegeben_wien,",
    "       v.abgelehnt_von, v.abgelehnt_am AT TIME ZONE 'Europe/Vienna' AS abgelehnt_wien,",
    "       (SELECT n.parameter->>'qualifikation' FROM meta.regel n",
    `         WHERE n.ersetzt_regel_id = ${literal(stand.regelId)} AND n.regelsatz = v.regelsatz_ziel AND n.aktiv) AS ziel_spalte`,
    "FROM meta.vorschlag v",
    `WHERE v.regelsatz_basis = ${literal(stand.regelsatz)}`,
    "  AND EXISTS (SELECT 1 FROM jsonb_array_elements(v.aenderungen) a",
    `              WHERE a->>'regel_name' = ${literal(stand.regelName)})`,
    "ORDER BY v.id DESC LIMIT 1;",
  ].join("\n");
}

function isoText(wert: unknown): string | null {
  if (wert instanceof Date) return wert.toISOString();
  return typeof wert === "string" && wert ? wert : null;
}

async function ladeKategorieStand(sql: Sql, regelsatz: string): Promise<KategorieStand | null> {
  const [r] = await sql<{ id: number; name: string; spalte: string | null }[]>`
    SELECT id, name, parameter->>'qualifikation' AS spalte FROM meta.regel
    WHERE regelsatz = ${regelsatz} AND aktiv AND parameter ? 'qualifikation'
    ORDER BY id DESC LIMIT 1`;
  if (!r?.spalte) return null;
  const stand: KategorieStand = { regelsatz, regelId: Number(r.id), regelName: r.name, spalte: r.spalte, auftrag: null };
  const [da] = await sql`SELECT to_regclass('meta.vorschlag') IS NOT NULL AS da`;
  if (!da?.da) return stand;
  const [v] = await sql<
    {
      id: number;
      anweisung: string;
      status: string;
      regelsatz_ziel: string;
      freigegeben_von: string | null;
      freigegeben_am: Date | null;
      abgelehnt_von: string | null;
      abgelehnt_am: Date | null;
      ziel_spalte: string | null;
      vorschlag_spalte: string | null;
    }[]
  >`
    SELECT v.id, v.anweisung, v.status, v.regelsatz_ziel, v.freigegeben_von, v.freigegeben_am,
           v.abgelehnt_von, v.abgelehnt_am,
           (SELECT n.parameter->>'qualifikation' FROM meta.regel n
             WHERE n.ersetzt_regel_id = ${stand.regelId} AND n.regelsatz = v.regelsatz_ziel AND n.aktiv
             ORDER BY n.id DESC LIMIT 1) AS ziel_spalte,
           (SELECT a->'parameter_neu'->>'qualifikation' FROM jsonb_array_elements(v.aenderungen) a
             WHERE a->>'regel_name' = ${stand.regelName} LIMIT 1) AS vorschlag_spalte
    FROM meta.vorschlag v
    WHERE v.regelsatz_basis = ${regelsatz}
      AND EXISTS (SELECT 1 FROM jsonb_array_elements(v.aenderungen) a WHERE a->>'regel_name' = ${stand.regelName})
    ORDER BY v.id DESC LIMIT 1`;
  if (!v) return stand;
  const status = v.status === "freigegeben" || v.status === "abgelehnt" ? v.status : "offen";
  stand.auftrag = {
    vorschlagId: Number(v.id),
    titel: v.anweisung.split(":")[0]?.trim() || v.anweisung,
    status,
    regelsatzZiel: v.regelsatz_ziel,
    zielSpalte: v.ziel_spalte ?? v.vorschlag_spalte,
    von: status === "freigegeben" ? v.freigegeben_von : status === "abgelehnt" ? v.abgelehnt_von : null,
    am: isoText(status === "freigegeben" ? v.freigegeben_am : status === "abgelehnt" ? v.abgelehnt_am : null),
  };
  return stand;
}

const WIEN = new Intl.DateTimeFormat("de-AT", {
  timeZone: "Europe/Vienna",
  day: "numeric",
  month: "long",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

/** „5. November 2026 um 16:53 Uhr“ in Wiener Zeit. */
export function wienerZeit(iso: string): string {
  const teile = Object.fromEntries(WIEN.formatToParts(new Date(iso)).map((t) => [t.type, t.value]));
  return `${teile.day}. ${teile.month} ${teile.year} um ${teile.hour}:${teile.minute} Uhr`;
}

/** Wie ein Regelsatz die Qualifikationen zählt, als Satz aus der Spalte der Zählregel. */
function zaehltSatz(regelsatz: string, spalte: string | null, liste: readonly Qualifikation[]): string {
  const bekannt = liste.filter((q) => q.code !== UNBEKANNT);
  const kategorien = [...new Set(bekannt.map((q) => q.kategorie))];
  const und = (xs: string[]) => (xs.length < 2 ? (xs[0] ?? "") : `${xs.slice(0, -1).join(", ")} und ${xs.at(-1)}`);
  if (spalte === "code") {
    return `In Regelsatz ${regelsatz} zählen wir die ${bekannt.length} gelieferten Qualifikationen einzeln, wie geliefert: ${und(bekannt.map((q) => q.bezeichnung))}.`;
  }
  if (spalte === "beschaeftigungskategorie") {
    return `In Regelsatz ${regelsatz} fassen wir die ${bekannt.length} Qualifikationen zu ${kategorien.length} Beschäftigungskategorien zusammen: ${und(kategorien)}. Dienstvertrag und freier Dienstvertrag zählen gemeinsam.`;
  }
  return `In Regelsatz ${regelsatz} zählen wir die Qualifikation nach der Spalte „${spalte ?? "unbekannt"}“.`;
}

/**
 * Sätze zur Zählregel der Qualifikation, alles aus der Datenbank: wie der Regelsatz der Seite zählt, ob ein Auftrag
 * das ändert und in welchem Stand er ist (mit Name und Wiener Zeit), und mit welchem Regelsatz die Zahlen der Seite
 * gerechnet sind. Kein fester Text über den Freigabestand.
 */
export function kategorieSaetze(
  stand: KategorieStand,
  liste: readonly Qualifikation[],
  zahlenRegelsatz: string | null,
): { regel: string; auftrag: string | null; zahlen: string | null } {
  const regel = zaehltSatz(stand.regelsatz, stand.spalte, liste);
  const a = stand.auftrag;
  const kurz = a ? (a.titel.split(",")[0]?.trim() ?? a.titel) : "";
  let auftrag: string | null = null;
  if (a?.status === "offen") {
    auftrag = `„${a.titel}“ wartet auf Freigabe. Gezählt wird mit Regelsatz ${stand.regelsatz}, bis ${kurz} freigegeben ist.`;
  } else if (a?.status === "freigegeben") {
    const wer = a.von && a.am ? ` von ${a.von} am ${wienerZeit(a.am)}` : "";
    auftrag = `„${a.titel}“ ist als Regelsatz ${a.regelsatzZiel} freigegeben${wer}. ${zaehltSatz(a.regelsatzZiel, a.zielSpalte, liste)}`;
  } else if (a?.status === "abgelehnt") {
    const wer = a.von && a.am ? ` von ${a.von} am ${wienerZeit(a.am)}` : "";
    auftrag = `„${a.titel}“ ist abgelehnt${wer}. Gezählt wird weiter mit Regelsatz ${stand.regelsatz}.`;
  }
  const zahlen = zahlenRegelsatz ? `Die Zahlen auf dieser Seite sind mit Regelsatz ${zahlenRegelsatz} gerechnet.` : null;
  return { regel, auftrag, zahlen };
}

// ---------------------------------------------------------------------------------------------------------------
// ÖNACE-Abschnitte nach Namen: eine Zeile je Branche, daneben ihr Buchstabe 2008 und 2025

export type NamensVergleich = "gleich" | "gewechselt" | "neu" | "entfaellt";

export interface NamensZeile {
  bezeichnung: string;
  codeAlt: string | null;
  codeNeu: string | null;
  vergleich: NamensVergleich;
}

/**
 * Ordnet die Abschnitte nach ihrem Namen statt nach dem Buchstaben: „Gesundheits- und Sozialwesen“ steht einmal da,
 * 2008 unter Q und 2025 unter R. Alphabetisch nach Namen, „unbekannt“ am Ende.
 */
export function abschnitteNachName(zeilen: readonly AbschnittZeile[]): NamensZeile[] {
  const nachName = new Map<string, { codeAlt: string | null; codeNeu: string | null }>();
  const eintrag = (name: string) =>
    nachName.get(name) ?? nachName.set(name, { codeAlt: null, codeNeu: null }).get(name)!;
  for (const z of zeilen) {
    if (z.alt) eintrag(z.alt.bezeichnung).codeAlt = z.alt.code;
    if (z.neu) eintrag(z.neu.bezeichnung).codeNeu = z.neu.code;
  }
  const ergebnis: NamensZeile[] = [...nachName].map(([bezeichnung, { codeAlt, codeNeu }]) => ({
    bezeichnung,
    codeAlt,
    codeNeu,
    vergleich: !codeAlt ? "neu" : !codeNeu ? "entfaellt" : codeAlt === codeNeu ? "gleich" : "gewechselt",
  }));
  const unbekannt = (z: NamensZeile) => z.codeAlt === UNBEKANNT || z.codeNeu === UNBEKANNT;
  return ergebnis.sort(
    (a, b) => Number(unbekannt(a)) - Number(unbekannt(b)) || a.bezeichnung.localeCompare(b.bezeichnung, "de"),
  );
}
