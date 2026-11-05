/** Tastatur und Adresse der Folienschau (#59). Reine Funktionen, Folien zählen ab 1. */

const VOR = new Set(["ArrowRight", " ", "PageDown"]);
const ZURUECK = new Set(["ArrowLeft", "PageUp"]);

/**
 * Folie nach einem Tastendruck. Am Anfang und am Ende bleibt die Schau stehen (kein Umbruch).
 * `null` heißt: diese Taste gehört nicht zur Navigation, der Browser behandelt sie wie sonst.
 */
export function naechsteFolie(aktuell: number, anzahl: number, taste: string): number | null {
  let ziel: number;
  if (VOR.has(taste)) ziel = aktuell + 1;
  else if (ZURUECK.has(taste)) ziel = aktuell - 1;
  else if (taste === "Home") ziel = 1;
  else if (taste === "End") ziel = anzahl;
  else return null;
  return Math.min(Math.max(ziel, 1), Math.max(anzahl, 1));
}

export type Schalter = "vollbild" | "notizen";

/** F schaltet Vollbild, N die Sprecher-Notizen (Groß- und Kleinschreibung gleich). */
export function schalterFuerTaste(taste: string): Schalter | null {
  const klein = taste.toLowerCase();
  return klein === "f" ? "vollbild" : klein === "n" ? "notizen" : null;
}

/** Folie aus `?folie=N`. Nur ganze Zahlen von 1 bis `anzahl` zählen, alles andere ergibt Folie 1. */
export function folieAusParam(wert: string | readonly string[] | undefined, anzahl: number): number {
  const erster = Array.isArray(wert) ? wert[0] : wert;
  if (typeof erster !== "string" || !/^\d{1,6}$/.test(erster)) return 1;
  const n = Number(erster);
  return n >= 1 && n <= anzahl ? n : 1;
}
