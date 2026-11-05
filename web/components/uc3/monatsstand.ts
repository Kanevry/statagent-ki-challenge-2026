import { verschieben } from "./monat";
import type { Monatslauf } from "./typen";

// Reine Regeln der Monatsübersicht (/uc3), ohne React; getestet in monatsstand.test.ts.

export type Stand = { art: "ok" | "warnung" | "fehler" | "info"; wort: string };

/** Stand eines Monats: ein angehaltener Monat bleibt vorläufig, das steht dabei. */
export function monatsStand(monat: Pick<Monatslauf, "angehalten" | "ergebnisStand"> & { gehtAuf: boolean }): Stand {
  if (!monat.gehtAuf) return { art: "fehler", wort: "Abrechnung geht nicht auf" };
  if (monat.angehalten) return { art: "warnung", wort: "angehalten, vorläufig" };
  if (monat.ergebnisStand === "endgueltig") return { art: "ok", wort: "veröffentlicht" };
  return { art: "info", wort: "vorläufig" };
}

/**
 * Vergleichsmonat für „zum Vormonat“: der Kalendermonat davor, nur wenn er in der Liste steht. Sonst „erster Monat“
 * (nichts davor gerechnet) oder „Vormonat fehlt“ (Lücke in der Liste).
 */
export function vormonatIn(
  monat: Pick<Monatslauf, "lieferung">,
  monate: readonly Pick<Monatslauf, "lieferung">[],
): { lieferung: string } | "erster Monat" | "Vormonat fehlt" {
  const davor = verschieben(monat.lieferung, -1);
  if (monate.some((m) => m.lieferung === davor)) return { lieferung: davor };
  return monate.some((m) => m.lieferung < monat.lieferung) ? "Vormonat fehlt" : "erster Monat";
}
