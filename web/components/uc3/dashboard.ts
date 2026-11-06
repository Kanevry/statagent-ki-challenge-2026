import { einstufungAus, massgeblichMit, type EinstufungCode } from "./bericht";
import { literal } from "./beleg";
import { lies, type Lesung, type Sql } from "./db";
import { gruppeAus, gruppeVon } from "./einstufung-gruppen";
import { ladeLaufDetail, type LaufDetail } from "./lauf-detail";
import { MASSGEBLICH_SQL } from "./laeufe";
import { monatName, monatsgrenzen } from "./monat";
import type { Lauf, Monatslauf } from "./typen";
import { bestandFilter } from "./zeitraum";

// Daten des Dashboards auf /uc3. Gezählt wird nur in der Datenbank, hier stehen Abfragen und die Sätze dazu.
// Jede Abfrage eines Belegs liefert die Zahl, die daneben steht; ausgeführt wird die parametrisierte Fassung.

export type EinstufungsZahl = { code: EinstufungCode; wort: string; anzahl: number };
export type Gruppe = { code: string; name: string; anzahl: number };

/** Feste Reihenfolge: zuerst, was die Fachabteilung klären muss. Fehlende Einstufungen stehen mit 0 da. */
const REIHE: readonly EinstufungCode[] = ["nicht-erklaerbar", "erklaert-datenproblem", "erklaert-plausibel"];

export function einstufungsReihe(zeilen: readonly { einstufung: string | null; anzahl: string | number }[]): EinstufungsZahl[] {
  return REIHE.map((code) => ({
    code,
    wort: gruppeVon(gruppeAus(code)).kurz,
    anzahl: zeilen.filter((z) => einstufungAus(z.einstufung).code === code).reduce((summe, z) => summe + Number(z.anzahl), 0),
  }));
}

function einstufungenSql(ausdruck: string): string {
  return [
    "WITH massgeblich AS (",
    massgeblichMit(ausdruck)
      .split("\n")
      .map((z) => `  ${z}`)
      .join("\n"),
    ")",
    "SELECT coalesce(t.einstufung, 'nicht-erklaerbar') AS einstufung, count(*) AS anzahl",
    "FROM massgeblich m JOIN meta.pruefung_treffer t ON t.lauf_id = m.quelle_id AND t.anzahl > 0",
    "GROUP BY 1 ORDER BY 1;",
  ].join("\n");
}

/** Auffälligkeiten aller Monate nach Einstufung, je Monat aus dem maßgeblichen Lauf. */
export function sqlEinstufungen(regelsatz: string): string {
  return einstufungenSql(literal(regelsatz));
}

/** Monate insgesamt und davon vorläufig, je Monat der maßgebliche Lauf. */
export function sqlVorlaeufig(regelsatz: string): string {
  return [
    "SELECT count(*) AS monate, count(*) FILTER (WHERE ergebnis_status <> 'endgueltig') AS vorlaeufig",
    `FROM (${MASSGEBLICH_SQL.replace("$1", literal(regelsatz)).split("\n").join("\n      ")}) m;`,
  ].join("\n");
}

/** Bestand je Geschlecht. Der Regelstand gehört in den Filter, sonst zählt ein neu gerechneter Monat doppelt. */
export function sqlGeschlecht(lauf: Pick<Lauf, "lieferung" | "regelsatz" | "regelstand" | "zeitraumArt">): string {
  const { von, bis } = monatsgrenzen(lauf.lieferung);
  return [
    "SELECT s.geschlecht, k.bezeichnung, sum(s.wert) AS beschaeftigungsverhaeltnisse",
    "FROM stat.stat_beschaeftigte s",
    "LEFT JOIN stat.klass_geschlecht k ON k.code = s.geschlecht",
    `WHERE s.regelsatz = ${literal(lauf.regelsatz)} AND s.regelstand = ${literal(lauf.regelstand)}`,
    `  AND ${bestandFilter(lauf.zeitraumArt, "s.")}`,
    `  AND s.zeitraum_bis BETWEEN ${literal(von)} AND ${literal(bis)}`,
    "GROUP BY 1, 2 ORDER BY 3 DESC;",
  ].join("\n");
}

async function ladeGeschlecht(sql: Sql, lauf: Lauf): Promise<Gruppe[]> {
  const { von, bis } = monatsgrenzen(lauf.lieferung);
  const zeilen = await sql<{ geschlecht: string; bezeichnung: string | null; anzahl: string }[]>`
    SELECT s.geschlecht, k.bezeichnung, sum(s.wert) AS anzahl
    FROM stat.stat_beschaeftigte s
    LEFT JOIN stat.klass_geschlecht k ON k.code = s.geschlecht
    WHERE s.regelsatz = ${lauf.regelsatz} AND s.regelstand = ${lauf.regelstand}
      AND s.zeitraum_art = ${lauf.zeitraumArt} AND s.variable = 'Beschaeftigungsverhaeltnisse'
      AND s.zeitraum_bis BETWEEN ${von} AND ${bis}
    GROUP BY 1, 2
    ORDER BY 3 DESC`;
  return zeilen.map((z) => ({ code: z.geschlecht, name: z.bezeichnung ?? `Code ${z.geschlecht}`, anzahl: Number(z.anzahl) }));
}

export type DashboardDaten = { detail: LaufDetail; einstufungen: EinstufungsZahl[]; geschlecht: Gruppe[] };

/** Alles, was über die Monatsübersicht hinausgeht. Ohne Antwort zeigt /uc3 die Seite ohne diese Blöcke. */
export function leseDashboard(letzter: Lauf, regelsatz: string): Promise<Lesung<DashboardDaten | null>> {
  return lies(async (sql) => {
    const [detail, einstufungen, geschlecht] = await Promise.all([
      ladeLaufDetail(sql, letzter.lieferung, regelsatz),
      // Fester Abfragetext aus diesem Modul, der Regelsatz geht als Parameter $1 hinein.
      sql.unsafe<{ einstufung: string | null; anzahl: string }[]>(einstufungenSql("$1"), [regelsatz]),
      ladeGeschlecht(sql, letzter),
    ]);
    return detail ? { detail, einstufungen: einstufungsReihe(einstufungen), geschlecht } : null;
  });
}

/** Kopfsatz: was gerechnet ist und wie die Monate stehen, aus den Läufen gezählt. */
export function kopfSatz(monate: readonly Pick<Monatslauf, "angehalten" | "ergebnisStand">[]): string {
  const angehalten = monate.filter((m) => m.angehalten).length;
  const frei = monate.filter((m) => !m.angehalten);
  const veroeffentlicht = frei.filter((m) => m.ergebnisStand === "endgueltig").length;
  const vorlaeufig = frei.length - veroeffentlicht;
  const teile = [
    veroeffentlicht > 0 ? `${veroeffentlicht} veröffentlicht` : null,
    vorlaeufig > 0 ? `${vorlaeufig} vorläufig` : null,
    angehalten > 0 ? `${angehalten} angehalten` : null,
  ].filter((t) => t !== null);
  return `${monate.length} Monate gerechnet: ${teile.join(", ")}.`;
}

/** Satz unter der Zahl der vorläufigen Monate: wenige werden genannt, alle zusammengefasst. */
export function vorlaeufigSatz(monate: readonly Pick<Monatslauf, "lieferung" | "ergebnisStand">[]): string {
  const vorlaeufig = monate.filter((m) => m.ergebnisStand !== "endgueltig");
  if (vorlaeufig.length === 0) return "Alle Monate sind veröffentlicht.";
  if (vorlaeufig.length === monate.length) return "Mit diesen Regeln ist noch kein Monat veröffentlicht.";
  if (vorlaeufig.length > 3) return "Diese Monate sind noch nicht veröffentlicht.";
  const namen = vorlaeufig.map((m) => monatName(m.lieferung));
  const liste = namen.length > 1 ? `${namen.slice(0, -1).join(", ")} und ${namen.at(-1)}` : namen[0];
  return `${liste} ${namen.length > 1 ? "sind" : "ist"} noch nicht veröffentlicht.`;
}

/** Balkenlänge in Prozent der größten Gruppe; die Balken beginnen immer bei null. */
export function balkenProzent(anzahl: number, groesste: number): number {
  return groesste > 0 ? Math.max(0, (anzahl / groesste) * 100) : 0;
}
