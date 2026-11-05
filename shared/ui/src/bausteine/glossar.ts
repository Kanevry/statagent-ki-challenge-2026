// Glossar der StatAgent-Begriffe in Alltagssprache. Die 14 Begriffe des UC3-Panels liegen nicht im
// Repo; bis dahin die fünf Begriffe, die jede Seite braucht. Ergänzen: Eintrag hier, `Begriff` findet ihn.
export const GLOSSAR = {
  Lieferung: "Die Daten, die die Sozialversicherungsträger jeden Monat schicken.",
  Revisionsbedarf:
    "Eine schon veröffentlichte Zahl wäre mit den neuen Daten anders. Sie bleibt stehen, der Unterschied kommt in den Qualitätsbericht.",
  Qualitätsbericht: "Bericht zu jeder Lieferung: was geprüft wurde, was auffiel und was das für die Zahlen heißt.",
  Freigabe: "Ein Mensch bestätigt mit Vor- und Nachname, dass eine Änderung gilt. Ohne Freigabe ändert sich nichts.",
  Beleg: "Zeigt, woher eine Zahl kommt: aus welcher Lieferung und mit welcher Abfrage sie gerechnet wurde.",
} as const satisfies Record<string, string>;

export type GlossarWort = keyof typeof GLOSSAR;
