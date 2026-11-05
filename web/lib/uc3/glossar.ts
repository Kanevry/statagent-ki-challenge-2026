// Fachbegriffe des StatAgent in Alltagssprache (Persona-Panel 05.11., Stimme ux-verstaendlichkeit), ergänzt um die
// Wörter, die die UC3-Seiten zusätzlich brauchen. Jede Erklärung ist ein Satz ohne weiteren Fachbegriff.
// Das gemeinsame Glossar in @kic/ui gehört E0; dieses hier gilt nur für /uc3.

export const UC3_GLOSSAR = {
  Lieferung: "Die Monatsdatei, die wir von der Sozialversicherung bekommen.",
  Vollabzug: "Jede Datei enthält die letzten drei Monate noch einmal ganz.",
  Stichtag: "Wir zählen, wer am letzten Tag des Monats beschäftigt war.",
  Beschäftigungsverhältnis: "Ein Job einer Person bei einem Arbeitgeber; eine Person kann zwei haben.",
  Monatslauf: "Das Programm rechnet einen Monat aus seiner Lieferung, ohne KI und jedes Mal gleich.",
  Auffälligkeit: "Etwas sieht anders aus als erwartet und braucht ein Urteil.",
  Einstufung: "Das Urteil zu einer Auffälligkeit: echte Entwicklung, Datenfehler oder unklar.",
  Regel: "Eine schriftliche Abmachung, wie gezählt wird.",
  Regelstand: "Die Fassung aller Regeln, mit der ein Monat gerechnet wurde.",
  Annahme: "Wir mussten etwas festlegen und schreiben dazu, warum.",
  Klassifikation: "Die offizielle Liste der Codes, zum Beispiel für Branchen oder Bundesländer.",
  Klassifikationswechsel: "Ab Jänner 2025 gilt eine neue Liste der Branchen.",
  Revisionsbedarf: "Eine spätere Lieferung zeigt, dass eine schon gezeigte Zahl heute anders wäre; die alte bleibt stehen.",
  Freigabe: "Ein Mensch sagt mit Vor- und Nachnamen: Ja, so rechnen wir ab jetzt.",
  Rückfrage: "Wir fragen die Fachabteilung, statt zu raten.",
  Qualitätsbericht: "Der Bericht zu jedem Monat: was geprüft wurde, was auffiel und was das für die Zahlen heißt.",
  Beleg: "Zeigt, woher eine Zahl kommt: aus welcher Lieferung und mit welcher Abfrage.",
  vorläufig: "Die Zahl kann sich noch ändern, bis ein Mensch den Monat freigibt.",
  fortgeschrieben: "Fehlen Verhältnisse in einer Lieferung, übernehmen wir sie aus dem Vormonat und sagen das dazu.",
  Abrechnung: "Jeder gelesene Satz ist entweder gezählt, nicht gezählt oder ausgeschlossen; keiner geht verloren.",
} as const satisfies Record<string, string>;

export type Uc3Begriff = keyof typeof UC3_GLOSSAR;
