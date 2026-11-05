/**
 * Worüber ein Regelsatz zählt: v1 am Stichtag (Monatsletzter), nach Auftrag 2 über das ganze Monat. Die Art steht in
 * der Bestandsregel (`meta.regel`, Parameter `zeitraum_art`) und in jeder Zelle von `stat.stat_beschaeftigte`. Abfragen
 * und Texte fragen hier nach, statt „Stichtag“ fest zu schreiben: Ein fester Filter liefert für v2 keine einzige Zeile.
 * Gleiche Quelle wie `zaehl_zeitraum` in uc3/statagent/berichte/sheet.py.
 */
export type ZeitraumArt = "Stichtag" | "Monat";

/** Unbekannt oder keine Bestandsregel: wie die Fachbeschreibung, also Stichtag. */
export function zeitraumArtAus(wert: string | null | undefined): ZeitraumArt {
  return wert === "Monat" ? "Monat" : "Stichtag";
}

/** SQL-Ausdruck für die Zeitraumart des Regelsatzes; `alias` ist der Name von meta.lauf (fester Text aus diesem Code). */
export function zeitraumArtSql(alias: "m" | "l"): string {
  return [
    "(SELECT r.parameter->>'zeitraum_art' FROM meta.regel r",
    `  WHERE r.regelsatz = ${alias}.regelsatz AND r.typ = 'zaehl' AND r.art = 'bestand' AND r.aktiv LIMIT 1)`,
  ].join("\n");
}

/** Filter auf die Bestandszeilen; `spalte` ist der Tabellenalias mit Punkt („s.“) oder leer. */
export function bestandFilter(art: ZeitraumArt, spalte = ""): string {
  return `${spalte}zeitraum_art = '${art}' AND ${spalte}variable = 'Beschaeftigungsverhaeltnisse'`;
}

/** „am Stichtag“ oder „im Monat“, für Tabellenköpfe und Worte unter einer Zahl. */
export function imZeitraum(art: ZeitraumArt): string {
  return art === "Monat" ? "im Monat" : "am Stichtag";
}

/** Tabellentitel über alle Monate. „im Monat je Monat“ wäre doppelt, deshalb trägt nur der Stichtag ein Zeitwort. */
export function bestandJeMonat(art: ZeitraumArt): string {
  return art === "Monat" ? "Beschäftigungsverhältnisse je Monat" : "Beschäftigungsverhältnisse am Stichtag je Monat";
}

/** Spaltenname im Beleg, passend zum Text darüber. */
export function bestandSpalte(art: ZeitraumArt): string {
  return art === "Monat" ? "bestand_im_monat" : "bestand_am_stichtag";
}

/**
 * Gespeicherte Befundtexte der Prüfregeln sagen „am Stichtag“. Zählt der Regelsatz über das Monat, heißt es
 * „im Berichtsmonat“; das Alter gilt weiter am Stichtag. Gleiche Regel wie `im_zeitraum` in qualitaetsbericht.py.
 */
export function imZeitraumText(text: string, art: ZeitraumArt): string {
  return art === "Monat" ? text.replace(/(?<!Jahren )am Stichtag/g, "im Berichtsmonat") : text;
}
