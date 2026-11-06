/**
 * Die drei Gruppen, in die eine Auffälligkeit fällt. Die Zuordnung kommt nur aus der gespeicherten Einstufung, hier wird
 * nichts umgestuft. „erklärt, plausibel“ heißt bewusst nicht „echte Entwicklung“: Darin stecken Saison und Nachmeldungen,
 * aber auch echte Menschen ab 75 Jahren und einzelne Stornos (gemessen 06.11.2026 an P07, P14, P16, P23).
 */
export type GruppeArt = "fehler" | "kein-fehler" | "offen";

export interface Gruppe {
  art: GruppeArt;
  titel: string;
  /** Kurzform für Sätze mit einer Zahl davor, etwa „103 Fehler in den Daten“. */
  kurz: string;
  satz: string;
  /** Wort der Qualitätsbericht-Vorlage, das in der aufgeklappten Zeile steht. */
  vorlage: string;
  zeichen: string;
  /** Schriftfarbe in der Tabelle; das Zeichen trägt die Bedeutung auch ohne Farbe. */
  farbe: string;
}

export const GRUPPEN: readonly Gruppe[] = [
  {
    art: "fehler",
    titel: "Fehler in den Daten",
    kurz: "Fehler in den Daten",
    satz: "Die Ursache ist bekannt, eine feste Regel behandelt sie.",
    vorlage: "erklärt, Datenproblem",
    zeichen: "✕",
    farbe: "text-err-fg",
  },
  {
    art: "kein-fehler",
    titel: "Kein Fehler: echt oder üblich",
    kurz: "kein Fehler",
    satz: "Ungewohnt, aber echt oder üblich, etwa Saison oder Nachmeldungen. Zählt mit und wird vermerkt.",
    vorlage: "erklärt, plausibel",
    zeichen: "✓",
    farbe: "text-gruen",
  },
  {
    art: "offen",
    titel: "Noch nicht erklärt",
    kurz: "noch nicht erklärt",
    satz: "Das Programm rät nicht, ein Mensch muss es klären.",
    vorlage: "nicht erklärbar",
    zeichen: "?",
    farbe: "text-warn-fg",
  },
];

/** Ohne Einstufung gilt ein Treffer wie im Qualitätsbericht-Generator als nicht erklärbar. */
export function gruppeAus(einstufung: string | null | undefined): GruppeArt {
  if (einstufung === "erklaert-datenproblem") return "fehler";
  if (einstufung === "erklaert-plausibel") return "kein-fehler";
  return "offen";
}

export function gruppeVon(art: GruppeArt): Gruppe {
  return GRUPPEN.find((g) => g.art === art) as Gruppe;
}

/** Einträge je Gruppe in fester Reihenfolge; die Reihenfolge innerhalb bleibt, leere Gruppen fallen weg. */
export function inGruppen<T extends { einstufung: string | null }>(
  liste: readonly T[],
): { gruppe: Gruppe; eintraege: T[] }[] {
  return GRUPPEN.map((gruppe) => ({
    gruppe,
    eintraege: liste.filter((t) => gruppeAus(t.einstufung) === gruppe.art),
  })).filter((g) => g.eintraege.length > 0);
}
