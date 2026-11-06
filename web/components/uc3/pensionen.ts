import { lies, type Lesung, type Sql } from "./db";
import { standName } from "./klassifikation-tief";

/**
 * Pensionsstatistik 2018 bis 2025 (#77) für /uc3/pensionen. Nur lesend. Die Summen über die Träger bildet die Seite aus
 * `stat.stat_pensionen`; Tabelle 13 ist ein Teil der Alterspensionen und wird nicht zu Tabelle 12 addiert. Vor dem Laden
 * (`uv run uc3 pensionen laden`) fehlen die Zeilen, und die Seite zeigt ihren Leerzustand.
 */

export const SQL_PENSIONEN = `SELECT extract(year FROM s.zeitraum_von)::int AS jahr, a.uebergeordnet AS tabelle,
  s.versicherungstraeger AS traeger, sum(s.wert) AS wert, bool_or(s.status <> 'endgueltig') AS vorlaeufig
FROM stat.stat_pensionen s
JOIN stat.klass_pensionsart a ON a.code = s.pensionsart
GROUP BY 1, 2, 3
ORDER BY 1, 2, 3`;

export const SQL_TRAEGER = `SELECT code, bezeichnung, ebene, uebergeordnet
FROM stat.klass_versicherungstraeger
ORDER BY ebene, gueltig_von, code = 'PV-SEL', code`;

export const SQL_TABELLEN = `SELECT code, bezeichnung FROM stat.klass_pensionsart WHERE ebene = 1 ORDER BY code`;

export const SQL_ZUSAMMENLEGUNG = `SELECT u.code_alt, u.code_neu, u.gueltig_ab::text AS gueltig_ab
FROM stat.uebergang u
JOIN stat.klass_versicherungstraeger alt ON alt.code = u.code_alt AND alt.ebene = 3
JOIN stat.klass_versicherungstraeger neu ON neu.code = u.code_neu AND neu.ebene = 3
WHERE u.klassifikation = 'versicherungstraeger'
ORDER BY u.code_neu, u.code_alt`;

export const SQL_LADUNG = `SELECT count(*) AS dateien, count(DISTINCT l.regel_name) AS formate,
  (SELECT count(*) FROM meta.pension_summe) AS summen,
  (SELECT count(*) FROM meta.pension_summe WHERE gemeldet <> gerechnet) AS abweichend,
  min(l.freigegeben_von) AS freigegeben_von, min(l.freigegeben_am)::date::text AS freigegeben_am
FROM meta.pension_ladung l`;

export interface PensionsZeile {
  code: string;
  name: string;
  ebene: number;
  /** Je Jahr der Tabelle ein Wert; `null`: In diesem Jahr gibt es von diesem Träger keine Meldung. */
  werte: (number | null)[];
}

export interface PensionsTabelle {
  code: string;
  titel: string;
  zeilen: PensionsZeile[];
}

export interface Pensionsdaten {
  jahre: number[];
  tabellen: PensionsTabelle[];
  /** `true`, solange die Zahlen nicht mit Namen freigegeben sind. */
  vorlaeufig: boolean;
  freigabe: { name: string; am: string | null } | null;
  zusammenlegung: string | null;
  /** Erstes Jahr nach der Zusammenlegung: Dort trennt eine Linie die Tabelle. */
  bruchJahr: number | null;
  fehlt: string[];
  pruefung: string | null;
}

type Wert = { jahr: number; tabelle: string; traeger: string; wert: string | number; vorlaeufig: boolean };
type Traeger = { code: string; bezeichnung: string; ebene: number; uebergeordnet: string | null };
type Tabelle = { code: string; bezeichnung: string };
type Zusammenlegung = { code_alt: string; code_neu: string; gueltig_ab: string };
type Ladung = {
  dateien: string | number;
  formate: string | number;
  summen: string | number;
  abweichend: string | number;
  freigegeben_von: string | null;
  freigegeben_am: string | null;
};

/** „a, b und c“. */
function liste(teile: readonly (string | number)[]): string {
  if (teile.length < 2) return teile.join("");
  return `${teile.slice(0, -1).join(", ")} und ${teile.at(-1)}`;
}

function zeileName(t: Traeger): string {
  return t.ebene === 3 ? `${t.bezeichnung} (${t.code})` : t.bezeichnung;
}

/**
 * Eine Tabelle in der Gliederung der Träger: Summen vor ihren Teilen, je Knoten die Summe seiner Teile. Ein Träger ohne
 * Meldung in dieser Tabelle hat keine Zeile; ein Jahr ohne Meldung bleibt leer und wird nicht zu 0.
 */
export function pensionsZeilen(traeger: readonly Traeger[], werte: readonly Wert[], jahre: readonly number[]): PensionsZeile[] {
  const eigene = new Map<string, Map<number, number>>();
  for (const w of werte) {
    const jeJahr = eigene.get(w.traeger) ?? new Map<number, number>();
    jeJahr.set(Number(w.jahr), Number(w.wert));
    eigene.set(w.traeger, jeJahr);
  }
  const zeilen: PensionsZeile[] = [];
  const besuche = (t: Traeger): (number | null)[] => {
    const stelle = zeilen.length;
    const summe = jahre.map((j) => eigene.get(t.code)?.get(j) ?? null);
    for (const kind of traeger.filter((k) => k.uebergeordnet === t.code)) {
      besuche(kind).forEach((wert, i) => {
        if (wert !== null) summe[i] = (summe[i] ?? 0) + wert;
      });
    }
    if (summe.some((wert) => wert !== null)) zeilen.splice(stelle, 0, { code: t.code, name: zeileName(t), ebene: t.ebene, werte: summe });
    return summe;
  };
  for (const wurzel of traeger.filter((t) => t.uebergeordnet === null)) besuche(wurzel);
  return zeilen;
}

/** Der Satz zum Wechsel der Träger, aus `stat.uebergang`. */
export function zusammenlegungSatz(zeilen: readonly Zusammenlegung[]): string | null {
  const erste = zeilen[0];
  if (!erste) return null;
  const jeNachfolger = new Map<string, string[]>();
  for (const z of zeilen) jeNachfolger.set(z.code_neu, [...(jeNachfolger.get(z.code_neu) ?? []), z.code_alt]);
  const teile = [...jeNachfolger].map(([neu, alt], i) => `${liste(alt)} ${i === 0 ? "wurde " : ""}die ${neu}`);
  return `Zum ${standName(erste.gueltig_ab)} wurden Träger zusammengelegt. Aus ${teile.join(", aus ")}. Die Zahlen davor und danach stehen unverändert nebeneinander.`;
}

/** Was in den Meldungen fehlt. Jeder Satz steht nur, wenn die Daten ihn tragen. */
export function fehltSaetze(werte: readonly Wert[]): string[] {
  const melden = (code: string, tabelle?: string) =>
    werte.filter((w) => w.traeger.split("-")[0] === code && (tabelle === undefined || w.tabelle === tabelle));
  const saetze: string[] = [];
  if (melden("BVA").length === 0 && melden("BVAEB").length > 0) {
    saetze.push("Öffentlich Bedienstete fehlen in allen Jahren, die frühere BVA meldet keine Pensionen. Die BVAEB steht deshalb nur mit Eisenbahn und Bergbau in der Tabelle.");
  }
  const notariat = melden("VAN", "T12");
  if (notariat.length > 0 && melden("VAN", "T13").length === 0) {
    const jahre = liste([...new Set(notariat.map((w) => Number(w.jahr)))].sort());
    saetze.push(`Bei den vorzeitigen Alterspensionen fehlt ${jahre} das Notariat (VAN), es meldet diese Art nicht.`);
  }
  return saetze;
}

/** Was beim Laden nachgerechnet wurde. */
export function pruefSatz(l: Ladung | undefined): string | null {
  const dateien = Number(l?.dateien ?? 0);
  if (!l || dateien === 0) return null;
  const abweichend = Number(l.abweichend);
  const ergebnis = abweichend === 0 ? "keine weicht ab" : `${abweichend} weichen ab`;
  return `${dateien} Dateien in ${Number(l.formate)} Formaten gelesen. ${Number(l.summen)} Summen aus den Dateien nachgerechnet, ${ergebnis}.`;
}

/** Macht aus den Zeilen der Abfragen die Daten der Seite; der Treiber liefert große Summen als Text. */
export function pensionsdaten(
  werte: readonly Wert[],
  traeger: readonly Traeger[],
  tabellen: readonly Tabelle[],
  zusammenlegung: readonly Zusammenlegung[],
  ladung: Ladung | undefined,
): Pensionsdaten {
  const jahre = [...new Set(werte.map((w) => Number(w.jahr)))].sort((a, b) => a - b);
  return {
    jahre,
    tabellen: tabellen
      .map((t) => ({
        code: t.code,
        titel: t.bezeichnung,
        zeilen: pensionsZeilen(traeger, werte.filter((w) => w.tabelle === t.code), jahre),
      }))
      .filter((t) => t.zeilen.length > 0),
    vorlaeufig: werte.some((w) => w.vorlaeufig),
    freigabe: ladung?.freigegeben_von ? { name: ladung.freigegeben_von, am: ladung.freigegeben_am } : null,
    zusammenlegung: werte.length > 0 ? zusammenlegungSatz(zusammenlegung) : null,
    bruchJahr: zusammenlegung[0] ? Number(zusammenlegung[0].gueltig_ab.slice(0, 4)) : null,
    fehlt: fehltSaetze(werte),
    pruefung: pruefSatz(ladung),
  };
}

const LEER: Pensionsdaten = { jahre: [], tabellen: [], vorlaeufig: false, freigabe: null, zusammenlegung: null, bruchJahr: null, fehlt: [], pruefung: null };

export async function lesePensionen(optionen: { sql?: Sql | null } = {}): Promise<Lesung<Pensionsdaten>> {
  return lies(async (sql) => {
    const [da] = await sql<{ pensionen: boolean; ladung: boolean }[]>`
      SELECT to_regclass('stat.stat_pensionen') IS NOT NULL AS pensionen,
             to_regclass('meta.pension_ladung') IS NOT NULL AND to_regclass('meta.pension_summe') IS NOT NULL AS ladung`;
    if (!da?.pensionen) return LEER;
    const [werte, traeger, tabellen, zusammenlegung, ladung] = await Promise.all([
      sql.unsafe<Wert[]>(SQL_PENSIONEN),
      sql.unsafe<Traeger[]>(SQL_TRAEGER),
      sql.unsafe<Tabelle[]>(SQL_TABELLEN),
      sql.unsafe<Zusammenlegung[]>(SQL_ZUSAMMENLEGUNG),
      da.ladung ? sql.unsafe<Ladung[]>(SQL_LADUNG) : Promise.resolve([] as Ladung[]),
    ]);
    return pensionsdaten(werte, traeger, tabellen, zusammenlegung, ladung[0]);
  }, optionen);
}
