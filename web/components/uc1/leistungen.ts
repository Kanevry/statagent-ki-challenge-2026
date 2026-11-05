// Anzeigenamen der Leistungen, die der Lotse als Bündel kennt. Quelle: `name.de` in uc1/daten/leistungen.yaml
// (Daten des Kerns); leistungen.test.ts prüft, dass jede Leistung der Datei hier mit gleichem Namen steht, sobald sie
// im Checkout liegt. Ein Name darf hier schon stehen, bevor der Kern ihn liefert.
export const LEISTUNGEN: Readonly<Record<string, string>> = {
  pflegegeld: "Pflegegeld",
  pflegekarenzgeld: "Pflegekarenzgeld",
  rehabilitation: "Rehabilitation und Kur",
  krankengeld: "Krankengeld",
  wochengeld: "Wochengeld",
  unfallversicherung: "Unfallversicherung",
};

/** Anzeigename einer Leistung; eine unbekannte ID wird lesbar gemacht („zahn_spange“ → „Zahn spange“). */
export function leistungName(id: string): string {
  const bekannt = LEISTUNGEN[id];
  if (bekannt) return bekannt;
  const woerter = id.replace(/[_-]+/g, " ").trim();
  return woerter ? woerter.charAt(0).toUpperCase() + woerter.slice(1) : id;
}

const ZAHLWOERTER = ["", "", "Zwei", "Drei", "Vier", "Fünf", "Sechs", "Sieben", "Acht", "Neun", "Zehn"];

/**
 * Überschrift der Leistungen (Urteil ui-regie-32): bei einer „Pflegegeld kommt für Sie in Frage“, bei mehreren
 * „Zwei Leistungen kommen für Sie in Frage“; die Namen stehen dann in den Karten. Die Person („für Ihre Mutter“)
 * nennt der Kern nicht sicher, deshalb immer „für Sie“.
 */
export function leistungenTitel(ids: readonly string[]): string {
  if (ids.length <= 1) return `${leistungName(ids[0] ?? "")} kommt für Sie in Frage`;
  return `${ZAHLWOERTER[ids.length] ?? ids.length} Leistungen kommen für Sie in Frage`;
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
