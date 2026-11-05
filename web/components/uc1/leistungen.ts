// Anzeigenamen der Leistungen, die der Lotse als Bündel kennt. Quelle: `name.de` in uc1/daten/leistungen.yaml
// (Daten des Kerns); leistungen.test.ts prüft die Zuordnung gegen die Datei, sobald sie im Checkout liegt.
export const LEISTUNGEN: Readonly<Record<string, string>> = {
  pflegegeld: "Pflegegeld",
  pflegekarenzgeld: "Pflegekarenzgeld",
  rehabilitation: "Rehabilitation und Kur",
  krankengeld: "Krankengeld",
  wochengeld: "Wochengeld",
};

/** Anzeigename einer Leistung; eine unbekannte ID wird lesbar gemacht („zahn_spange“ → „Zahn spange“). */
export function leistungName(id: string): string {
  const bekannt = LEISTUNGEN[id];
  if (bekannt) return bekannt;
  const woerter = id.replace(/[_-]+/g, " ").trim();
  return woerter ? woerter.charAt(0).toUpperCase() + woerter.slice(1) : id;
}

/**
 * Anträge des Kerns heißen nicht immer wie ihre Leistung (`reha` gehört zu `rehabilitation`). Nur Anzeige: so steht
 * der Antrag-Knopf bei der richtigen Leistung und der Antrag trägt deren Namen.
 */
export const ANTRAG_LEISTUNG: Readonly<Record<string, string>> = { reha: "rehabilitation" };

/** Leistung, zu der ein Antrag gehört. */
export function antragLeistung(art: string): string {
  return ANTRAG_LEISTUNG[art] ?? art;
}

/** Anzeigename eines Antrags, über seine Leistung („reha“ → „Rehabilitation und Kur“). */
export function antragName(art: string): string {
  return leistungName(antragLeistung(art));
}
