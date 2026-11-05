import type { UcNavPunkt } from "@kic/ui/shell";

/**
 * Unter-Navigation von /uc3. Lauf-Details (/uc3/laeufe/…) gehören zu „Monatsläufe“. Nur gebaute Seiten stehen
 * hier: das Anti-Schablonen-Gate folgt jedem Link und verlangt HTTP 200.
 */
export const UC3_NAVIGATION: readonly UcNavPunkt[] = [
  // UI-Regie Version 1: drei Schritte der Vorführung, dann ruhig „Regeln und Klassifikationen“. Berichte gehören
  // zu „Monate“ (die Monatsseite ist zugleich der Qualitätsbericht); die Routen bleiben erreichbar.
  { href: "/uc3", label: "Monate" },
  { href: "/uc3/freigaben", label: "Freigaben" },
  { href: "/uc3/fragen", label: "Fragen an die Daten" },
  { href: "/uc3/klassifikationen", label: "Regeln und Klassifikationen" },
];

export type Regelsatz = "v1" | "v2";

/** Regelsatz aus einem Such-Parameter: nur „v2“ gilt, alles andere ist v1 (Standard der Fachbeschreibung). */
export function regelsatzAus(wert: string | string[] | undefined): Regelsatz {
  return wert === "v2" ? "v2" : "v1";
}

function mitRegelsatz(pfad: string, regelsatz: string): string {
  return regelsatz === "v2" ? `${pfad}?regelsatz=v2` : pfad;
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
