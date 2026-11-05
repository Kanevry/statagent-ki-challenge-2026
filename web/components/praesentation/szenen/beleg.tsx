import { absatzTexte, kopfzeile, zahlWert } from "../../../lib/praesentation/szenen-daten";
import { Blick, Fuss, Haken, k, Kreis, Raster, vars, Zaehler, type SzeneProps } from "./gemeinsam";

// Gestaltung: 96 Spalten wie im Prototyp (2.880 Zellen ergeben 30 Zeilen).
const SPALTEN = 96;

/**
 * Szene 5: Raster mit so vielen Zellen wie `zahl`, die Zahl zählt hoch (Gelb), danach zeichnet sich ein großer
 * Mint-Haken über das Raster. Kreis 3 neben dem Titel.
 */
export function BelegSzene({ folie, nr, aktiv }: SzeneProps) {
  const ziel = zahlWert(folie.daten.zahl);
  const [satz] = absatzTexte(folie);
  return (
    <>
      <Kreis n={3} x={120} y={92} d={72} t={0} />
      <h2 className={k("titel", "a")} style={vars({ t: 0.1 })}>
        {kopfzeile(folie)}
      </h2>
      {Number.isFinite(ziel) && ziel > 0 && (
        <div className={k("s5-feld")} aria-hidden="true">
          <Raster anzahl={ziel} spalten={SPALTEN} aktiv={aktiv} />
          <Haken klasse="s5-haken" viewBox="0 0 1246 388" d="M440 210l150 120L840 50" t={2.1} dauer={0.8} />
        </div>
      )}
      <Zaehler ziel={ziel} aktiv={aktiv} start={300} className={k("s5-gross")} />
      {satz && (
        <p className={k("s5-satz", "a")} style={vars({ t: 2.9 })}>
          {satz}
        </p>
      )}
      <Blick folie={folie} breite={560} t={3.3} />
      <Fuss folie={folie} nr={nr} />
    </>
  );
}
