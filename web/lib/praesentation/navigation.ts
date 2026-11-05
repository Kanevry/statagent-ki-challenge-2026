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

/** Stand der Schau: Folie ab 1, Takt ab 0 (0 = noch kein Takt gezeigt). */
export interface Stand {
  folie: number;
  takt: number;
}

/**
 * Stand nach einem Tastendruck, mit Takten innerhalb einer Szene. `takte[i]` ist die Taktzahl von Folie i + 1.
 * Vor: erst den nächsten Takt, dann die nächste Folie (dort Takt 0). Zurück: erst einen Takt zurück, dann die
 * vorige Folie mit allen Takten. `alleTakte` (reduzierte Bewegung): jede betretene Folie zeigt sofort alle Takte,
 * Vor und Zurück überspringen die Takte und gehen direkt zur nächsten bzw. vorigen Folie.
 * `null` heißt wie bei `naechsteFolie`: die Taste gehört nicht zur Navigation.
 */
export function naechsterStand(stand: Stand, takte: readonly number[], taste: string, alleTakte = false): Stand | null {
  const anzahl = Math.max(takte.length, 1);
  const max = (folie: number) => Math.max(takte[folie - 1] ?? 0, 0);
  const betreten = (folie: number, vonHinten = false): Stand => ({
    folie,
    takt: vonHinten || alleTakte ? max(folie) : 0,
  });
  const folie = Math.min(Math.max(stand.folie, 1), anzahl);
  const takt = Math.min(Math.max(stand.takt, 0), max(folie));

  if (VOR.has(taste)) {
    if (!alleTakte && takt < max(folie)) return { folie, takt: takt + 1 };
    return folie < anzahl ? betreten(folie + 1) : { folie, takt: alleTakte ? max(folie) : takt };
  }
  if (ZURUECK.has(taste)) {
    if (!alleTakte && takt > 0) return { folie, takt: takt - 1 };
    return folie > 1 ? betreten(folie - 1, true) : { folie, takt };
  }
  if (taste === "Home") return betreten(1);
  if (taste === "End") return betreten(anzahl);
  return null;
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
