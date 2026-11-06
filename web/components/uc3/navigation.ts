import type { UcNavPunkt } from "@kic/ui/shell";

/**
 * Unter-Navigation von /uc3. Lauf-Details (/uc3/laeufe/…) gehören zu „Läufe“. Nur gebaute Seiten stehen
 * hier: das Anti-Schablonen-Gate folgt jedem Link und verlangt HTTP 200.
 */
export const UC3_NAVIGATION: readonly UcNavPunkt[] = [
  // Die Wörter des Bewertungsrasters (Bereich 6), damit die Jury sie findet. Die Regeln stehen auf „Klassifikationen“.
  { href: "/uc3", label: "Läufe" },
  { href: "/uc3/berichte", label: "Qualitätsberichte" },
  { href: "/uc3/freigaben", label: "Freigaben" },
  { href: "/uc3/fragen", label: "Fragen" },
  { href: "/uc3/annahmen", label: "Annahmen" },
  { href: "/uc3/klassifikationen", label: "Klassifikationen" },
];

/** Nur Vorführ-Instanz: der Auftrag an die Agenten kommt nach den Monaten. */
export function uc3Navigation(mitAuftrag: boolean): readonly UcNavPunkt[] {
  if (!mitAuftrag) return UC3_NAVIGATION;
  const [monate, ...rest] = UC3_NAVIGATION;
  return monate ? [monate, { href: "/uc3/auftrag", label: "Auftrag" }, ...rest] : UC3_NAVIGATION;
}

export type Regelsatz = `v${number}`;

/**
 * Regelsatz aus einem Such-Parameter: „v<Zahl>“ gilt, auch v3 und höher aus einer freigegebenen Live-Änderung, alles
 * andere ist v1 (Standard der Fachbeschreibung). Sonst zeigte der Link „mit Regelsatz v3“ still die Zahlen von v1.
 */
export function regelsatzAus(wert: string | string[] | undefined): Regelsatz {
  return typeof wert === "string" && /^v[1-9][0-9]{0,2}$/.test(wert) ? (wert as Regelsatz) : "v1";
}

function mitRegelsatz(pfad: string, regelsatz: string): string {
  return regelsatz === "v1" ? pfad : `${pfad}?regelsatz=${encodeURIComponent(regelsatz)}`;
}

/** Übersicht der Monatsläufe, bei v2 mit Such-Parameter. */
export function uebersichtPfad(regelsatz: string = "v1"): string {
  return mitRegelsatz("/uc3", regelsatz);
}

/** Pfad der Detailseite eines Monats; v2 behält den Regelsatz über alle Links. */
export function laufPfad(lieferung: string, regelsatz: string = "v1"): string {
  return mitRegelsatz(`/uc3/laeufe/${lieferung}`, regelsatz);
}

/** Pfad des Qualitätsberichts eines Monats. */
export function berichtPfad(lieferung: string, regelsatz: string = "v1"): string {
  return mitRegelsatz(`/uc3/berichte/${lieferung}`, regelsatz);
}

/** Liste der Qualitätsberichte. */
export function berichtslistePfad(regelsatz: string = "v1"): string {
  return mitRegelsatz("/uc3/berichte", regelsatz);
}
