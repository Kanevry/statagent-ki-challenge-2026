/**
 * Vertrag zwischen Datenzugriff (web/landing/daten/befunde.ts) und der Tabelle „Gefundene Datenfehler“.
 * Von der Koordination festgelegt, nur gemeinsam ändern.
 */
import type { Einstufung } from "./fakten";

export interface BefundZeile {
  befund: string;
  /** JJJJ-MM, Bereich oder „alle“ */
  lieferung: string;
  /** Anzeige mit deutschen Tausenderpunkten */
  saetze: string;
  einstufung: Einstufung;
  einstufungText: string;
  rueckfrage?: string;
  /** Kurzer Beleg (Abfrage-Ausschnitt) */
  beleg?: string;
}

export interface BefundTabelle {
  /** „datenbank“: aus meta.pruefung_treffer; „beispieldaten“: Fixture der Gegenrechnung, weil die DB fehlt */
  quelle: "datenbank" | "beispieldaten";
  zeilen: BefundZeile[];
  /** Zeilenzahl; bei „datenbank“ = select count(*) from meta.pruefung_treffer */
  anzahl: number;
  /** Zeitpunkt der Abfrage, ISO-8601 */
  stand: string;
}
