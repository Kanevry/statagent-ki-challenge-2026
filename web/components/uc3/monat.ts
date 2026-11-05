// Berichtsmonate als Text „JJJJ-MM“ (wie meta.lauf.lieferung). Keine Zeitzonen: Monatsgrenzen sind Kalendertage.

const MONATE = [
  "Jänner",
  "Februar",
  "März",
  "April",
  "Mai",
  "Juni",
  "Juli",
  "August",
  "September",
  "Oktober",
  "November",
  "Dezember",
] as const;

const MUSTER = /^(\d{4})-(0[1-9]|1[0-2])$/;

/** Ist der Text ein Berichtsmonat wie „2025-10“? Prüft auch Routen-Parameter. */
export function istMonat(text: string): boolean {
  return MUSTER.test(text);
}

function teile(monat: string): [number, number] {
  const treffer = MUSTER.exec(monat);
  if (!treffer) throw new Error(`Kein Berichtsmonat: ${monat}`);
  return [Number(treffer[1]), Number(treffer[2])];
}

/** „2024-08“ → „August 2024“ (österreichisch: Jänner). */
export function monatName(monat: string): string {
  const [jahr, nummer] = teile(monat);
  return `${MONATE[nummer - 1]} ${jahr}`;
}

/** Letzter Tag des Monats als Zahl. */
function letzterTag(jahr: number, nummer: number): number {
  return new Date(Date.UTC(jahr, nummer, 0)).getUTCDate();
}

/** Stichtag (Monatsletzter) als „31.08.2024“. */
export function stichtag(monat: string): string {
  const [jahr, nummer] = teile(monat);
  return `${String(letzterTag(jahr, nummer)).padStart(2, "0")}.${String(nummer).padStart(2, "0")}.${jahr}`;
}

/** Erster und letzter Tag als ISO-Datum, für Abfragen über `zeitraum_bis`. */
export function monatsgrenzen(monat: string): { von: string; bis: string } {
  const [jahr, nummer] = teile(monat);
  const mm = String(nummer).padStart(2, "0");
  return { von: `${jahr}-${mm}-01`, bis: `${jahr}-${mm}-${String(letzterTag(jahr, nummer)).padStart(2, "0")}` };
}

/** Monat davor bzw. danach: verschieben("2025-01", -1) = „2024-12“. */
export function verschieben(monat: string, monate: number): string {
  const [jahr, nummer] = teile(monat);
  const index = jahr * 12 + (nummer - 1) + monate;
  return `${String(Math.floor(index / 12)).padStart(4, "0")}-${String((index % 12) + 1).padStart(2, "0")}`;
}
