import { formatZahl } from "@kic/ui/bausteine";
import { monatName } from "./monat";
import daten from "./oenace-wechsel.json";

/**
 * Wechsel der ÖNACE in einem Berichtsmonat (#179). Die Zahlen stehen in einer erzeugten Datei (`uv run uc3 oenace-wechsel`,
 * Daten-Test in uc3/tests/test_oenace_wechsel_datei.py), weil online die Tabelle `bereinigt.abschnitt` fehlt.
 */
export interface OenaceWechsel {
  version_alt: string;
  version_neu: string;
  vormonat: string;
  stichtag: string;
  gesamt: number;
  anders: number;
  nur_buchstabe: number;
  beispiel: { name: string; alt: string; neu: string; anzahl: number };
  beleg_sql: string;
}

const JE_MONAT: Record<string, Record<string, OenaceWechsel | undefined> | undefined> = daten;

/** Der Wechsel dieses Monats oder `null`: Fast jeder Monat hat keinen, dann zeigt die Seite nichts dazu. */
export function oenaceWechsel(lieferung: string, regelsatz: string): OenaceWechsel | null {
  return JE_MONAT[lieferung]?.[regelsatz] ?? null;
}

export function wechselTitel(w: OenaceWechsel): string {
  return `Ab diesem Monat gilt ÖNACE ${w.version_neu} statt ÖNACE ${w.version_alt}.`;
}

/** Was der Wechsel bedeutet: zuerst die Folge für die Zahlen, dann der Umfang. */
export function wechselSaetze(w: OenaceWechsel, lieferung: string): [string, string] {
  const b = w.beispiel;
  return [
    "Zahlen je Abschnitt sind über den Wechsel nicht direkt vergleichbar, die Gesamtzahl ändert sich dadurch nicht. Das ist eine Umstellung, keine echte Entwicklung.",
    `Von ${formatZahl(w.gesamt)} Beschäftigungsverhältnissen, die am ${w.stichtag} in beiden Lieferungen stehen, tragen ${formatZahl(w.anders)} in der Lieferung ${monatName(lieferung)} einen anderen Abschnitt als in der Lieferung ${monatName(w.vormonat)}. Bei ${formatZahl(w.nur_buchstabe)} davon ist nur der Buchstabe neu, der Name bleibt: zum Beispiel „${b.name}“ von ${b.alt} zu ${b.neu} bei ${formatZahl(b.anzahl)}.`,
  ];
}
