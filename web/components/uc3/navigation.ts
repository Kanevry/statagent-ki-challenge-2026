import type { UcNavPunkt } from "@kic/ui/shell";

/**
 * Unter-Navigation von /uc3. Lauf-Details (/uc3/laeufe/…) gehören zu „Monatsläufe“. Nur gebaute Seiten stehen
 * hier: das Anti-Schablonen-Gate folgt jedem Link und verlangt HTTP 200.
 */
export const UC3_NAVIGATION: readonly UcNavPunkt[] = [
  { href: "/uc3", label: "Monatsläufe" },
  { href: "/uc3/berichte", label: "Qualitätsberichte" },
  { href: "/uc3/klassifikationen", label: "Klassifikationen" },
  { href: "/uc3/freigaben", label: "Freigaben" },
  { href: "/uc3/fragen", label: "Fragen an die Daten" },
];

/** Pfad der Detailseite eines Monats. */
export function laufPfad(lieferung: string): string {
  return `/uc3/laeufe/${lieferung}`;
}

/** Pfad des Qualitätsberichts eines Monats. */
export function berichtPfad(lieferung: string): string {
  return `/uc3/berichte/${lieferung}`;
}
