import { BEFUNDE } from "./fakten";
import type { BefundTabelle } from "./typen";

/** Die 8 Befunde der Gegenrechnung vom 05.11.2026 als Tabelle, sichtbar als „Beispieldaten“. */
export function befundeAusFixture(stand: string): BefundTabelle {
  return {
    quelle: "beispieldaten",
    zeilen: BEFUNDE.map((b) => ({
      befund: b.befund,
      lieferung: b.lieferung,
      saetze: b.saetze,
      einstufung: b.einstufung,
      einstufungText: b.einstufungText,
      rueckfrage: b.rueckfrage,
      beleg: b.beleg,
    })),
    anzahl: BEFUNDE.length,
    stand,
  };
}
