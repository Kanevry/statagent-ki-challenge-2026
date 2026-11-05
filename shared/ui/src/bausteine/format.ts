// Zahlen- und Zeitformat der Bausteine. Die Abbildung von Tausendertrennung (Punkt) und Minus (U+2212)
// kommt allein aus `formatiereZahl` der Basis, damit Bausteine und `<Zahl>` gleich schreiben.
import { formatiereZahl } from "../basis/text";

const GESCHUETZT = "\u00a0";

// −0 schreibt Intl als „−0“; eine Null ohne Vorzeichen ist gemeint.
function ohneMinusNull(wert: number): number {
  return Object.is(wert, -0) ? 0 : wert;
}

/** Zahl im Format 387.390, genau wie `formatiereZahl` aus `@kic/ui/basis`. */
export function formatZahl(wert: number): string {
  return formatiereZahl(ohneMinusNull(wert));
}

/** Differenz mit Vorzeichen: +12, −260, 0. */
export function formatDifferenz(wert: number): string {
  const text = formatZahl(wert);
  return wert > 0 ? `+${text}` : text;
}

/** Prozentwert mit zwei Nachkommastellen und Vorzeichen: −0,07 %. */
export function formatProzent(wert: number): string {
  // Kaufmännisch vom Betrag aus runden, wie Intl: −0,065 wird −0,07.
  const gerundet = ohneMinusNull((Math.sign(wert) * Math.round(Math.abs(wert) * 100)) / 100);
  const [ganz, nachkomma = ""] = formatDifferenz(gerundet).split(",");
  return `${ganz},${nachkomma.padEnd(2, "0")}${GESCHUETZT}%`;
}

/** Unterschied von vorher zu nachher; Prozent ist `null`, wenn vorher 0 ist. */
export function veraenderung(vorher: number, nachher: number): { differenz: number; prozent: number | null } {
  const diff = nachher - vorher;
  return { differenz: diff, prozent: vorher === 0 ? null : (diff / vorher) * 100 };
}

// Feste Zeitzone, damit Server und Browser dieselbe Uhrzeit ausgeben.
const zeitFormat = new Intl.DateTimeFormat("de-AT", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "Europe/Vienna",
});

/** ISO-Zeitpunkt als „05.11.2026, 10:12“; ein ungültiger Wert bleibt, wie er ist. */
export function formatZeit(iso: string): string {
  const datum = new Date(iso);
  return Number.isNaN(datum.getTime()) ? iso : zeitFormat.format(datum);
}
