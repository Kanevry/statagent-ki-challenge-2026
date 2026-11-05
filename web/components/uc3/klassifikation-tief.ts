import { datumLang } from "./klassifikation";
import { lies, type Lesung, type Sql } from "./db";

/**
 * Nachschlagen auf /uc3/klassifikationen: ÖNACE bis zur Unterklasse und Regionen je Stand (#189). Nur lesend, Quelle
 * sind die Tabellen, die `uc3 db init` aus dem Startpaket lädt. Die Statistik zählt nicht nach diesen Ebenen, deshalb
 * gibt es hier keine Zahlen zu den Codes. Ohne geladene Ebenen bleibt der Abschnitt weg (`leseNachschlagen`).
 */

export type Art = "oenace" | "region";

export interface Wahl {
  wert: string;
  name: string;
  /** Für Sätze, zum Beispiel „in ÖNACE 2025“ oder „im Stand vom 1. Jänner 2026“. */
  ort: string;
}

export interface Auswahl {
  oenace: Wahl[];
  region: Wahl[];
}

export interface Knoten {
  code: string;
  name: string;
  /** Ebene in Worten, zum Beispiel „Unterklasse“. */
  ebene: string;
  hatKinder: boolean;
  /** Was sich an diesem Code geändert hat, in ganzen Sätzen; leer, wenn nichts. */
  aenderungen: string[];
  /** Nur bei Treffern der Suche: Ebene und wozu der Code gehört, als fertiger Text (`pfadSatz`). */
  pfad?: string;
}

export interface Kinder {
  knoten: Knoten[];
  /** Zum Beispiel „24 Abteilungen“. */
  ueberschrift: string;
}

export interface Treffer {
  knoten: Knoten[];
  /** Alle Treffer; `knoten` zeigt höchstens `TREFFER_MAX` davon. */
  gesamt: number;
}

export const TREFFER_MAX = 30;

const EBENEN: Record<string, [string, string]> = {
  "1": ["Abschnitt", "Abschnitte"],
  "2": ["Abteilung", "Abteilungen"],
  "3": ["Gruppe", "Gruppen"],
  "4": ["Klasse", "Klassen"],
  "5": ["Unterklasse", "Unterklassen"],
  bundesland: ["Bundesland", "Bundesländer"],
  bezirk: ["Bezirk", "Bezirke"],
  gemeinde: ["Gemeinde", "Gemeinden"],
};

export function ebeneWort(ebene: string, anzahl = 1): string {
  const namen = EBENEN[ebene];
  if (!namen) return ebene;
  return anzahl === 1 ? namen[0] : namen[1];
}

/** „2026-01-01“ wird zu „1. Jänner 2026“. */
export function standName(version: string): string {
  const t = /^(\d{4})-(\d{2})-(\d{2})$/.exec(version);
  return t ? datumLang(`${t[3]}.${t[2]}.${t[1]}`) : version;
}

/**
 * Regionen stehen in der Quelle als „Graz(Stadt)“ und „Wien  1.,Innere Stadt“. Die Anzeige setzt die fehlenden Leerzeichen;
 * Datenbank und Beleg behalten den Namen wie geliefert, die Suche vergleicht deshalb ohne Leerzeichen.
 */
export function regionName(name: string): string {
  return name
    .replace(/\s*\(/g, " (")
    .replace(/,\s*/g, ", ")
    .replace(/\s+/g, " ")
    .trim();
}

/** Wozu ein Treffer gehört: „Klasse in Herstellung von Waren (C)“, „Gemeinde, Steiermark › Weiz“, oben nur die Ebene. */
export function pfadSatz(art: Art, ebene: string, pfad: string | undefined): string {
  if (!pfad) return ebene;
  return art === "oenace" ? `${ebene} in ${pfad}` : `${ebene}, ${pfad}`;
}

export function fassungName(art: Art, wert: string): string {
  return art === "oenace" ? `ÖNACE ${wert}` : `Stand ${standName(wert)}`;
}

/** Die Fassungen der Auswahl: ÖNACE und Stände mit tiefen Zeilen, die neueste zuerst. */
export function auswahlAus(oenace: readonly string[], staende: readonly string[]): Auswahl {
  const neuesteZuerst = (a: string, b: string) => b.localeCompare(a);
  return {
    oenace: [...oenace].sort(neuesteZuerst).map((wert) => ({ wert, name: fassungName("oenace", wert), ort: `in ÖNACE ${wert}` })),
    region: [...staende].sort(neuesteZuerst).map((wert) => ({ wert, name: fassungName("region", wert), ort: `im Stand vom ${standName(wert)}` })),
  };
}

// ---------------------------------------------------------------------------------------------------------------
// Anfrage prüfen

export type Anfrage =
  | { art: Art; fassung: string; was: "wurzel" }
  | { art: Art; fassung: string; was: "kinder"; unter: string }
  | { art: Art; fassung: string; was: "suche"; suche: string };

const CODE = /^[A-Za-z0-9 .-]{1,20}$/;
const SUCHE_MAX = 60;

/** Prüft die Parameter der Route; `null` bei allem, was nicht passt. Die Abfragen binden die Werte zusätzlich. */
export function anfrageAus(parameter: URLSearchParams): Anfrage | null {
  const art = parameter.get("art");
  const fassung = parameter.get("fassung") ?? "";
  if (art !== "oenace" && art !== "region") return null;
  if (!(art === "oenace" ? /^\d{4}$/ : /^\d{4}-\d{2}-\d{2}$/).test(fassung)) return null;
  const unter = parameter.get("unter");
  const suche = parameter.get("suche");
  if (unter !== null && suche !== null) return null;
  if (unter !== null) return CODE.test(unter) ? { art, fassung, was: "kinder", unter } : null;
  if (suche !== null) {
    const text = suche.trim();
    return text.length > 0 && text.length <= SUCHE_MAX && !/\p{Cc}/u.test(text) ? { art, fassung, was: "suche", suche: text } : null;
  }
  return { art, fassung, was: "wurzel" };
}

// ---------------------------------------------------------------------------------------------------------------
// Sätze zu Änderungen

export interface UebergangZeile {
  version_alt: string;
  code_alt: string;
  name_alt: string | null;
  version_neu: string;
  code_neu: string;
  name_neu: string | null;
}

const LISTE_MAX = 3;

/** Höchstens drei Namen; `rest` nach dem Fall im Satz: „auf … und 2 weitere“, „aus … und 2 weiteren“. */
function liste(teile: readonly string[], rest = "weitere"): string {
  const gezeigt = teile.slice(0, LISTE_MAX).join(", ");
  return teile.length > LISTE_MAX ? `${gezeigt} und ${teile.length - LISTE_MAX} ${rest}` : gezeigt;
}

function benannt(name: string | null, code: string): string {
  return name ? `${name} (${code})` : `(${code})`;
}

function nachDatum(zeilen: readonly UebergangZeile[]): UebergangZeile[][] {
  const gruppen = new Map<string, UebergangZeile[]>();
  for (const z of zeilen) gruppen.set(z.version_neu, [...(gruppen.get(z.version_neu) ?? []), z]);
  return [...gruppen.keys()].sort().map((d) => gruppen.get(d)!);
}

/** Was mit einer Gemeinde oder einem Bezirk geschah, von `stand` aus gesehen, ältestes zuerst. */
export function regionSaetze(code: string, stand: string, zeilen: readonly UebergangZeile[]): string[] {
  const saetze: string[] = [];
  for (const gruppe of nachDatum(zeilen)) {
    const datum = standName(gruppe[0]!.version_neu);
    const vorher = gruppe.filter((z) => z.code_neu === code && z.version_neu <= stand);
    const danach = gruppe.filter((z) => z.code_alt === code && z.version_alt >= stand);
    if (vorher.length > 1) {
      saetze.push(`Seit ${datum} zusammengelegt aus ${liste(vorher.map((z) => benannt(z.name_alt, z.code_alt)), "weiteren")}.`);
    } else if (vorher.length === 1) {
      const z = vorher[0]!;
      if (z.code_alt !== code) saetze.push(`Seit ${datum} mit diesem Code, davor ${z.name_alt === z.name_neu ? `(${z.code_alt})` : benannt(z.name_alt, z.code_alt)}.`);
      else if (z.name_alt !== z.name_neu && z.name_alt) saetze.push(`Seit ${datum} unter diesem Namen, davor ${z.name_alt}.`);
      else saetze.push(`Seit ${datum} mit geändertem Gebiet.`);
    }
    if (danach.length > 1) {
      saetze.push(`Ab ${datum} aufgeteilt auf ${liste(danach.map((z) => benannt(z.name_neu, z.code_neu)))}.`);
    } else if (danach.length === 1) {
      const z = danach[0]!;
      if (z.code_neu !== code) saetze.push(z.name_alt === z.name_neu ? `Ab ${datum} mit neuem Code (${z.code_neu}).` : `Ab ${datum} gehört das Gebiet zu ${benannt(z.name_neu, z.code_neu)}.`);
      else if (z.name_alt !== z.name_neu && z.name_neu) saetze.push(`Ab ${datum} mit neuem Namen: ${z.name_neu}.`);
      else saetze.push(`Ab ${datum} mit geändertem Gebiet.`);
    }
  }
  return saetze;
}

/**
 * Was mit einer Unterklasse beim Wechsel 2008 auf 2025 geschah. Bleibt der Code gleich und allein, ist nichts zu sagen:
 * Das gilt für die meisten, und ein Satz an jeder Zeile wäre nur Lärm.
 */
export function oenaceSaetze(code: string, fassung: string, zeilen: readonly UebergangZeile[]): string[] {
  const saetze: string[] = [];
  const nachher = zeilen.filter((z) => z.code_alt === code && z.version_alt === fassung);
  const vorher = zeilen.filter((z) => z.code_neu === code && z.version_neu === fassung);
  const ziele = [...nachher].sort((a, b) => a.code_neu.localeCompare(b.code_neu));
  const quellen = [...vorher].sort((a, b) => a.code_alt.localeCompare(b.code_alt));
  if (ziele.length > 1) {
    saetze.push(`Ab ÖNACE ${ziele[0]!.version_neu} aufgeteilt auf ${liste(ziele.map((z) => benannt(z.name_neu, z.code_neu)))}.`);
  } else if (ziele.length === 1 && ziele[0]!.code_neu !== code) {
    saetze.push(`Ab ÖNACE ${ziele[0]!.version_neu} heißt der Code ${benannt(ziele[0]!.name_neu, ziele[0]!.code_neu)}.`);
  }
  if (quellen.length > 1) {
    saetze.push(`In ÖNACE ${quellen[0]!.version_alt} waren das ${liste(quellen.map((z) => benannt(z.name_alt, z.code_alt)))}.`);
  } else if (quellen.length === 1 && quellen[0]!.code_alt !== code) {
    saetze.push(`In ÖNACE ${quellen[0]!.version_alt} war das ${benannt(quellen[0]!.name_alt, quellen[0]!.code_alt)}.`);
  }
  return saetze;
}

// ---------------------------------------------------------------------------------------------------------------
// Abfragen

type Roh = { code: string; bezeichnung: string; ebene: string; hat_kinder: boolean; uebergeordnet: string | null };

export const SQL_NACHSCHLAGEN = [
  "-- ÖNACE: Kinder eines Codes einer Fassung",
  "SELECT code, bezeichnung, ebene FROM stat.klass_oenace",
  "WHERE version = '2025' AND uebergeordnet = 'C 10.1' ORDER BY code;",
  "",
  "-- Regionen: Gemeinden eines Bezirks je Stand",
  "SELECT code, bezeichnung, ebene FROM stat.klass_region",
  "WHERE version = '2026-01-01' AND uebergeordnet = '701' ORDER BY code;",
  "",
  "-- Änderungen an Gemeinden und Bezirken, Unterklassen 2008 auf 2025",
  "SELECT * FROM stat.uebergang",
  "WHERE klassifikation IN ('gemeinde', 'bezirk', 'oenace_unterklasse');",
].join("\n");

async function aenderungen(sql: Sql, art: Art, fassung: string, zeilen: readonly Roh[]): Promise<Map<string, string[]>> {
  const ergebnis = new Map<string, string[]>();
  if (art === "oenace") {
    const codes = zeilen.filter((z) => String(z.ebene) === "5").map((z) => z.code);
    if (codes.length === 0) return ergebnis;
    const roh = await sql<UebergangZeile[]>`
      SELECT u.version_alt, u.code_alt, a.bezeichnung AS name_alt, u.version_neu, u.code_neu, n.bezeichnung AS name_neu
      FROM stat.uebergang u
      LEFT JOIN stat.klass_oenace a ON a.version = u.version_alt AND a.code = u.code_alt
      LEFT JOIN stat.klass_oenace n ON n.version = u.version_neu AND n.code = u.code_neu
      WHERE u.klassifikation = 'oenace_unterklasse'
        AND ((u.version_alt = ${fassung} AND u.code_alt = ANY(${codes}))
          OR (u.version_neu = ${fassung} AND u.code_neu = ANY(${codes})))`;
    for (const code of codes) {
      const saetze = oenaceSaetze(code, fassung, roh.filter((z) => z.code_alt === code || z.code_neu === code));
      if (saetze.length > 0) ergebnis.set(code, saetze);
    }
    return ergebnis;
  }
  const codes = zeilen.filter((z) => z.ebene === "bezirk" || z.ebene === "gemeinde").map((z) => z.code);
  if (codes.length === 0) return ergebnis;
  const roh = await sql<UebergangZeile[]>`
    SELECT u.version_alt, u.code_alt, a.bezeichnung AS name_alt, u.version_neu, u.code_neu, n.bezeichnung AS name_neu
    FROM stat.uebergang u
    LEFT JOIN stat.klass_region a ON a.version = u.version_alt AND a.code = u.code_alt
    LEFT JOIN stat.klass_region n ON n.version = u.version_neu AND n.code = u.code_neu
    WHERE u.klassifikation IN ('gemeinde', 'bezirk')
      AND ((u.code_alt = ANY(${codes}) AND u.version_alt >= ${fassung})
        OR (u.code_neu = ANY(${codes}) AND u.version_neu <= ${fassung}))`;
  for (const code of codes) {
    const saetze = regionSaetze(
      code,
      fassung,
      roh
        .filter((z) => z.code_alt === code || z.code_neu === code)
        .map((z) => ({
          ...z,
          name_alt: z.name_alt && regionName(z.name_alt),
          name_neu: z.name_neu && regionName(z.name_neu),
        })),
    );
    if (saetze.length > 0) ergebnis.set(code, saetze);
  }
  return ergebnis;
}

function anzeigeZeile(art: Art, zeile: Roh): Roh {
  return art === "region" ? { ...zeile, bezeichnung: regionName(zeile.bezeichnung) } : zeile;
}

async function alsKnoten(sql: Sql, art: Art, fassung: string, zeilen: readonly Roh[]): Promise<Knoten[]> {
  const saetze = await aenderungen(sql, art, fassung, zeilen);
  return zeilen.map((z) => ({
    code: z.code,
    name: anzeigeZeile(art, z).bezeichnung,
    ebene: ebeneWort(String(z.ebene)),
    hatKinder: Boolean(z.hat_kinder),
    aenderungen: saetze.get(z.code) ?? [],
  }));
}

function ueberschrift(zeilen: readonly Roh[]): string {
  const erste = zeilen[0];
  return erste ? `${zeilen.length} ${ebeneWort(String(erste.ebene), zeilen.length)}` : "";
}

function wurzelRoh(sql: Sql, art: Art, fassung: string) {
  // Die Abschnitte und Länder, unter denen es etwas gibt: „Wirtschaftszweig unbekannt“ und „Bundesland unbekannt“ fallen weg.
  return art === "oenace"
    ? sql<Roh[]>`
        SELECT k.code, k.bezeichnung, k.ebene::text AS ebene, true AS hat_kinder, k.uebergeordnet
        FROM stat.klass_oenace k
        WHERE k.version = ${fassung} AND k.ebene = 1
          AND EXISTS (SELECT 1 FROM stat.klass_oenace c WHERE c.version = k.version AND c.uebergeordnet = k.code)
        ORDER BY k.code COLLATE "C"`
    : sql<Roh[]>`
        SELECT k.code, k.bezeichnung, k.ebene, true AS hat_kinder, k.uebergeordnet
        FROM stat.klass_region k
        WHERE k.ebene = 'bundesland'
          AND EXISTS (SELECT 1 FROM stat.klass_region c WHERE c.version = ${fassung} AND c.uebergeordnet = k.code)
        ORDER BY k.code COLLATE "C"`;
}

function kinderRoh(sql: Sql, art: Art, fassung: string, unter: string) {
  return art === "oenace"
    ? sql<Roh[]>`
        SELECT k.code, k.bezeichnung, k.ebene::text AS ebene, k.uebergeordnet,
          EXISTS (SELECT 1 FROM stat.klass_oenace c WHERE c.version = k.version AND c.uebergeordnet = k.code) AS hat_kinder
        FROM stat.klass_oenace k
        WHERE k.version = ${fassung} AND k.uebergeordnet = ${unter}
        ORDER BY k.code COLLATE "C"`
    : sql<Roh[]>`
        SELECT k.code, k.bezeichnung, k.ebene, k.uebergeordnet, k.ebene = 'bezirk' AS hat_kinder
        FROM stat.klass_region k
        WHERE k.version = ${fassung} AND k.uebergeordnet = ${unter}
        ORDER BY k.code COLLATE "C"`;
}

function mitEscape(text: string): string {
  return text.replace(/[\\%_]/g, "\\$&");
}

type RohTreffer = Roh & { gesamt: string | number };

function sucheRoh(sql: Sql, art: Art, fassung: string, suche: string) {
  const roh = mitEscape(suche);
  // Bei einem Zeichen nur der Code: „C“ meint den Abschnitt, nicht jeden Namen mit einem c.
  const mitNamen = suche.length >= 2;
  const muster = `%${roh}%`;
  const anfang = `${roh}%`;
  // Regionen ohne Leerzeichen vergleichen: „Graz (Stadt)“ findet „Graz(Stadt)“ aus der Quelle.
  const dicht = mitEscape(suche.replace(/\s+/g, ""));
  if (art === "oenace") {
    const kompakt = mitEscape(suche.replace(/\s+/g, "").toUpperCase());
    return sql<RohTreffer[]>`
      SELECT k.code, k.bezeichnung, k.ebene::text AS ebene, k.uebergeordnet, count(*) OVER () AS gesamt,
        EXISTS (SELECT 1 FROM stat.klass_oenace c WHERE c.version = k.version AND c.uebergeordnet = k.code) AS hat_kinder
      FROM stat.klass_oenace k
      WHERE k.version = ${fassung} AND k.code <> 'UNB'
        AND (replace(upper(k.code), ' ', '') LIKE ${`${kompakt}%`}
          OR split_part(k.code, ' ', 2) LIKE ${`${roh}%`}
          OR (${mitNamen}::boolean AND k.bezeichnung ILIKE ${muster}))
      ORDER BY
        CASE
          WHEN replace(upper(k.code), ' ', '') = ${suche.replace(/\s+/g, "").toUpperCase()} OR split_part(k.code, ' ', 2) = ${suche} THEN 0
          WHEN replace(upper(k.code), ' ', '') LIKE ${`${kompakt}%`} OR split_part(k.code, ' ', 2) LIKE ${`${roh}%`} THEN 1
          WHEN k.bezeichnung ILIKE ${anfang} THEN 2
          ELSE 3
        END,
        k.code COLLATE "C"
      LIMIT ${TREFFER_MAX}`;
  }
  return sql<RohTreffer[]>`
    SELECT k.code, k.bezeichnung, k.ebene, k.uebergeordnet, count(*) OVER () AS gesamt, k.ebene <> 'gemeinde' AS hat_kinder
    FROM stat.klass_region k
    WHERE ((k.version = ${fassung} AND k.ebene IN ('bezirk', 'gemeinde')) OR (k.ebene = 'bundesland' AND k.code <> '0'))
      AND (k.code LIKE ${`${roh}%`}
        OR (${mitNamen}::boolean AND regexp_replace(k.bezeichnung, '[[:space:]]', '', 'g') ILIKE ${`%${dicht}%`}))
    ORDER BY
      CASE
        WHEN k.code = ${suche} THEN 0
        WHEN k.code LIKE ${`${roh}%`} THEN 1
        WHEN regexp_replace(k.bezeichnung, '[[:space:]]', '', 'g') ILIKE ${`${dicht}%`} THEN 2
        ELSE 3
      END,
      k.code COLLATE "C"
    LIMIT ${TREFFER_MAX}`;
}

/**
 * Wozu jeder Treffer gehört, je Ebene eine Abfrage. ÖNACE: nur der Abschnitt, die Kette über vier Ebenen wäre länger als
 * der Treffer selbst. Region: Bundesland und Bezirk, Österreich als Staat steht nicht dabei.
 */
async function pfade(sql: Sql, art: Art, fassung: string, zeilen: readonly Roh[]): Promise<Map<string, string>> {
  const bekannt = new Map<string, { name: string; oben: string | null }>();
  let offen = [...new Set(zeilen.map((z) => z.uebergeordnet).filter((c): c is string => Boolean(c)))];
  for (let tiefe = 0; offen.length > 0 && tiefe < 5; tiefe++) {
    const eltern =
      art === "oenace"
        ? await sql<{ code: string; bezeichnung: string; uebergeordnet: string | null }[]>`
            SELECT code, bezeichnung, uebergeordnet FROM stat.klass_oenace WHERE version = ${fassung} AND code = ANY(${offen})`
        : await sql<{ code: string; bezeichnung: string; uebergeordnet: string | null }[]>`
            SELECT code, bezeichnung, uebergeordnet FROM stat.klass_region
            WHERE version IN (${fassung}, 'BL') AND code = ANY(${offen}) AND ebene <> 'staat'`;
    for (const e of eltern) bekannt.set(e.code, { name: e.bezeichnung, oben: e.uebergeordnet });
    offen = [...new Set(eltern.map((e) => e.uebergeordnet).filter((c): c is string => Boolean(c) && !bekannt.has(c!)))];
  }
  const ergebnis = new Map<string, string>();
  for (const z of zeilen) {
    const teile: string[] = [];
    let c = z.uebergeordnet;
    while (c && bekannt.has(c)) {
      const e = bekannt.get(c)!;
      teile.unshift(art === "oenace" ? `${e.name} (${c})` : regionName(e.name));
      c = e.oben;
    }
    if (teile.length > 0) ergebnis.set(z.code, art === "oenace" ? teile[0]! : teile.join(" › "));
  }
  return ergebnis;
}

export function leseAnfrage(anfrage: Anfrage, optionen: { sql?: Sql | null } = {}): Promise<Lesung<Kinder | Treffer>> {
  return lies(async (sql) => {
    const { art, fassung } = anfrage;
    if (anfrage.was === "suche") {
      const roh = await sucheRoh(sql, art, fassung, anfrage.suche);
      const [knoten, pfad] = await Promise.all([alsKnoten(sql, art, fassung, roh), pfade(sql, art, fassung, roh)]);
      return {
        knoten: knoten.map((k) => ({ ...k, pfad: pfadSatz(art, k.ebene, pfad.get(k.code)) })),
        gesamt: roh[0] ? Number(roh[0].gesamt) : 0,
      };
    }
    const roh = anfrage.was === "wurzel" ? await wurzelRoh(sql, art, fassung) : await kinderRoh(sql, art, fassung, anfrage.unter);
    return { knoten: await alsKnoten(sql, art, fassung, roh), ueberschrift: ueberschrift(roh) };
  }, optionen);
}

/**
 * Was die Seite zum Start braucht: welche Fassungen und Stände es gibt, dazu die oberste Ebene der ersten Wahl.
 * `null` in `daten`, wenn die tiefen Ebenen nicht geladen sind; die Seite zeigt den Abschnitt dann nicht.
 */
export function leseNachschlagen(
  optionen: { sql?: Sql | null } = {},
): Promise<Lesung<{ auswahl: Auswahl; start: Kinder; art: Art } | null>> {
  return lies(async (sql) => {
    const [oenace, staende] = await Promise.all([
      sql<{ version: string }[]>`SELECT DISTINCT version FROM stat.klass_oenace WHERE ebene = 5`,
      sql<{ version: string }[]>`SELECT DISTINCT version FROM stat.klass_region WHERE ebene = 'gemeinde'`,
    ]);
    const auswahl = auswahlAus(
      oenace.map((z) => z.version),
      staende.map((z) => z.version),
    );
    const art: Art | null = auswahl.oenace.length > 0 ? "oenace" : auswahl.region.length > 0 ? "region" : null;
    if (!art) return null;
    const roh = await wurzelRoh(sql, art, auswahl[art][0]!.wert);
    return {
      auswahl,
      art,
      start: { knoten: await alsKnoten(sql, art, auswahl[art][0]!.wert, roh), ueberschrift: ueberschrift(roh) },
    };
  }, optionen);
}
