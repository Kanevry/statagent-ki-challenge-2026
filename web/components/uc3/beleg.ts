import type { HerkunftChipProps } from "@kic/ui/bausteine";
import { monatsgrenzen } from "./monat";
import type { Lauf } from "./typen";

/** Belegdaten für `<HerkunftChip>`, ohne Darstellungs-Props. */
export type Beleg = Omit<HerkunftChipProps, "className">;

/**
 * Setzt einen Wert als SQL-Literal in einen Anzeige-Text. Nur für das SQL, das der Beleg ZEIGT; ausgeführt wird
 * immer die parametrisierte Fassung. Werte stammen aus der eigenen Datenbank (Regelstand, Monat), nie aus Eingaben.
 */
export function literal(wert: string | number): string {
  return typeof wert === "number" ? String(wert) : `'${wert.replaceAll("'", "''")}'`;
}

/** Abfrage, die die Zahl der Beschäftigungsverhältnisse eines Monats aus den Zellen summiert. */
export function sqlBestand(lauf: Pick<Lauf, "lieferung" | "regelsatz" | "regelstand">): string {
  const { von, bis } = monatsgrenzen(lauf.lieferung);
  return [
    "SELECT sum(wert) AS beschaeftigungsverhaeltnisse",
    "FROM stat.stat_beschaeftigte",
    `WHERE regelsatz = ${literal(lauf.regelsatz)} AND regelstand = ${literal(lauf.regelstand)}`,
    "  AND zeitraum_art = 'Stichtag' AND variable = 'Beschaeftigungsverhaeltnisse'",
    `  AND zeitraum_bis BETWEEN ${literal(von)} AND ${literal(bis)};`,
  ].join("\n");
}

/** Abfrage der Abrechnung eines Laufs: gelesen = gezählt + nicht gezählt + ausgeschlossen (ohne Fortgeschriebene). */
export function sqlAbrechnung(lauf: Pick<Lauf, "id">): string {
  return [
    "SELECT lieferung, gelesen, gezaehlt - fortgeschrieben AS gezaehlt_aus_lieferung,",
    "       nicht_gezaehlt, ausgeschlossen, fortgeschrieben",
    "FROM meta.lauf",
    `WHERE id = ${literal(lauf.id)};`,
  ].join("\n");
}

/**
 * Eine Abfrage für eine ganze Zeile der Monatsübersicht: Bestand aus den Zellen und die Abrechnung des Laufs.
 * So trägt jede Zahl der Zeile denselben Beleg.
 */
export function sqlMonatszeile(lauf: Pick<Lauf, "id" | "lieferung" | "regelsatz" | "regelstand">): string {
  const { von, bis } = monatsgrenzen(lauf.lieferung);
  return [
    "SELECT l.lieferung, l.gelesen, l.nicht_gezaehlt, l.ausgeschlossen, l.fortgeschrieben,",
    "       (SELECT sum(s.wert) FROM stat.stat_beschaeftigte s",
    `         WHERE s.regelsatz = l.regelsatz AND s.regelstand = l.regelstand`,
    "           AND s.zeitraum_art = 'Stichtag' AND s.variable = 'Beschaeftigungsverhaeltnisse'",
    `           AND s.zeitraum_bis BETWEEN ${literal(von)} AND ${literal(bis)}) AS beschaeftigungsverhaeltnisse`,
    "FROM meta.lauf l",
    `WHERE l.id = ${literal(lauf.id)};`,
  ].join("\n");
}

/** Gemeinsame Angaben eines Laufs für jeden Beleg, der aus ihm stammt. */
export function laufBeleg(lauf: Lauf, extra: Partial<Beleg> = {}): Beleg {
  return {
    quelle: "stat.stat_beschaeftigte",
    lieferung: lauf.lieferung,
    monat: lauf.lieferung,
    regelstand: lauf.regelstand,
    lauf: lauf.ergebnisHash,
    stand: lauf.ergebnisStand,
    ...extra,
  };
}

/** Beleg der Zahl „Beschäftigungsverhältnisse am Stichtag“ eines Laufs. */
export function bestandBeleg(lauf: Lauf): Beleg {
  return laufBeleg(lauf, { sql: sqlBestand(lauf) });
}

/** Beleg einer Zeile der Monatsübersicht (Bestand und Abrechnung in einer Abfrage). */
export function monatszeileBeleg(lauf: Lauf): Beleg {
  return laufBeleg(lauf, { quelle: "meta.lauf", sql: sqlMonatszeile(lauf) });
}

/** Beleg der Abrechnung eines Laufs (Quelle meta.lauf). */
export function abrechnungBeleg(lauf: Lauf): Beleg {
  return laufBeleg(lauf, { quelle: "meta.lauf", sql: sqlAbrechnung(lauf) });
}
